import json
import os
import uuid
import boto3
from datetime import datetime, timezone
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION_NAME"])
apigw = None  # Initialized per-invocation with WebSocket endpoint

DOCUMENTS_TABLE = os.environ["DOCUMENTS_TABLE"]
JOBS_TABLE = os.environ["JOBS_TABLE"]
CONNECTIONS_TABLE = os.environ["CONNECTIONS_TABLE"]
OPENSEARCH_ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"]
AWS_REGION_NAME = os.environ["AWS_REGION_NAME"]
DOCUMENTS_BUCKET = os.environ.get("DOCUMENTS_BUCKET", "")

documents_table = dynamodb.Table(DOCUMENTS_TABLE)
jobs_table = dynamodb.Table(JOBS_TABLE)
connections_table = dynamodb.Table(CONNECTIONS_TABLE)

BEDROCK_LLM_MODEL = "anthropic.claude-3-sonnet-20240229-v1:0"
BEDROCK_EMBED_MODEL = "amazon.titan-embed-text-v1"
INDEX_NAME = "documents"
CHUNK_SIZE = 1000  # characters per chunk


def lambda_handler(event, context):
    # Handle direct Q&A API calls (from API Gateway)
    if "httpMethod" in event:
        return handle_qa_request(event)

    # Handle SQS trigger (post-OCR AI analysis)
    for record in event.get("Records", []):
        message = json.loads(record["body"])
        process_document(message)


# ── Document Processing Pipeline ──────────────────────────────────────────────

def process_document(message):
    user_id = message["user_id"]
    document_id = message["document_id"]
    text_key = message["text_key"]

    _update_job(document_id, "AI_IN_PROGRESS")

    try:
        # Load extracted text from S3
        obj = s3.get_object(Bucket=DOCUMENTS_BUCKET, Key=text_key)
        text = obj["Body"].read().decode("utf-8")

        # Generate summary and keywords via Bedrock
        summary = generate_summary(text)
        keywords = extract_keywords(text)

        # Chunk and index into OpenSearch
        index_document(user_id, document_id, text, summary, keywords)

        # Update DynamoDB with AI results
        documents_table.update_item(
            Key={"user_id": user_id, "document_id": document_id},
            UpdateExpression="SET #s = :s, summary = :sum, keywords = :kw, updated_at = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "COMPLETE",
                ":sum": summary,
                ":kw": keywords,
                ":u": datetime.now(timezone.utc).isoformat(),
            },
        )

        _update_job(document_id, "COMPLETE")

        # Notify connected WebSocket clients
        notify_user(user_id, {
            "type": "PROCESSING_COMPLETE",
            "document_id": document_id,
            "summary": summary,
            "keywords": keywords,
        })

    except Exception as e:
        _update_job(document_id, "AI_FAILED", error=str(e))
        raise


# ── Bedrock: Summarization ─────────────────────────────────────────────────────

def generate_summary(text):
    prompt = (
        "You are a document analysis assistant. "
        "Please provide a concise summary (3-5 sentences) of the following document:\n\n"
        f"{text[:8000]}"  # Limit to first 8000 chars for prompt
    )
    return _invoke_claude(prompt)


def extract_keywords(text):
    prompt = (
        "Extract 10 key topics or keywords from the following document. "
        "Return them as a JSON array of strings, e.g. [\"keyword1\", \"keyword2\"]. "
        "Return ONLY the JSON array, no other text.\n\n"
        f"{text[:4000]}"
    )
    response = _invoke_claude(prompt)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Fallback: split by commas if LLM didn't return valid JSON
        return [k.strip().strip('"') for k in response.strip("[]").split(",")]


def _invoke_claude(prompt):
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = bedrock.invoke_model(modelId=BEDROCK_LLM_MODEL, body=body)
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


# ── Bedrock: Embeddings ────────────────────────────────────────────────────────

def get_embedding(text):
    body = json.dumps({"inputText": text[:8000]})
    response = bedrock.invoke_model(modelId=BEDROCK_EMBED_MODEL, body=body)
    result = json.loads(response["body"].read())
    return result["embedding"]


# ── OpenSearch: Indexing ───────────────────────────────────────────────────────

def _get_os_client():
    credentials = boto3.Session().get_credentials()
    auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        AWS_REGION_NAME,
        "es",
        session_token=credentials.token,
    )
    return OpenSearch(
        hosts=[{"host": OPENSEARCH_ENDPOINT, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )


def _ensure_index(client):
    if client.indices.exists(INDEX_NAME):
        return
    client.indices.create(INDEX_NAME, body={
        "mappings": {
            "properties": {
                "user_id":     {"type": "keyword"},
                "document_id": {"type": "keyword"},
                "chunk_id":    {"type": "keyword"},
                "text":        {"type": "text"},
                "summary":     {"type": "text"},
                "keywords":    {"type": "keyword"},
                "embedding":   {"type": "knn_vector", "dimension": 1536},
                "created_at":  {"type": "date"},
            }
        },
        "settings": {"index": {"knn": True}},
    })


def index_document(user_id, document_id, text, summary, keywords):
    client = _get_os_client()
    _ensure_index(client)

    # Split text into chunks
    chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

    for i, chunk in enumerate(chunks):
        embedding = get_embedding(chunk)
        chunk_id = f"{document_id}_chunk_{i}"

        client.index(
            index=INDEX_NAME,
            id=chunk_id,
            body={
                "user_id":     user_id,
                "document_id": document_id,
                "chunk_id":    chunk_id,
                "text":        chunk,
                "summary":     summary if i == 0 else "",
                "keywords":    keywords if i == 0 else [],
                "embedding":   embedding,
                "created_at":  datetime.now(timezone.utc).isoformat(),
            },
        )


# ── Q&A (RAG) ─────────────────────────────────────────────────────────────────

def handle_qa_request(event):
    user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
    body = json.loads(event.get("body") or "{}")
    question = body.get("question")
    document_id = body.get("document_id")  # optional — scope to one doc

    if not question:
        return _response(400, {"error": "question is required"})

    # Embed the question
    query_embedding = get_embedding(question)

    # Retrieve relevant chunks from OpenSearch
    context_chunks = semantic_search(user_id, query_embedding, document_id)

    if not context_chunks:
        return _response(200, {"answer": "No relevant content found for your question."})

    # Build RAG prompt
    context = "\n\n---\n\n".join(c["text"] for c in context_chunks)
    prompt = (
        "You are a helpful document assistant. "
        "Answer the user's question using ONLY the context below. "
        "If the answer is not in the context, say 'I could not find this in the documents'.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )

    answer = _invoke_claude(prompt)
    return _response(200, {
        "answer": answer,
        "sources": [{"document_id": c["document_id"], "chunk_id": c["chunk_id"]} for c in context_chunks],
    })


def semantic_search(user_id, query_embedding, document_id=None):
    client = _get_os_client()

    must_filters = [{"term": {"user_id": user_id}}]
    if document_id:
        must_filters.append({"term": {"document_id": document_id}})

    response = client.search(
        index=INDEX_NAME,
        body={
            "size": 5,
            "query": {
                "bool": {
                    "must": must_filters,
                    "should": [{
                        "knn": {
                            "embedding": {
                                "vector": query_embedding,
                                "k": 5,
                            }
                        }
                    }],
                }
            },
        },
    )

    return [hit["_source"] for hit in response["hits"]["hits"]]


# ── WebSocket Notifications ────────────────────────────────────────────────────

def notify_user(user_id, payload):
    # Find all active connections for this user
    result = connections_table.query(
        IndexName="user_id-index",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(user_id),
    )

    if not result.get("Items"):
        return

    # Get WebSocket management URL from env (set by Terraform after deploy)
    ws_endpoint = os.environ.get("WEBSOCKET_ENDPOINT", "")
    if not ws_endpoint:
        return

    apigw_mgmt = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=ws_endpoint,
    )

    message = json.dumps(payload)
    for conn in result["Items"]:
        try:
            apigw_mgmt.post_to_connection(
                ConnectionId=conn["connection_id"],
                Data=message.encode("utf-8"),
            )
        except apigw_mgmt.exceptions.GoneException:
            # Stale connection — remove it
            connections_table.delete_item(
                Key={"connection_id": conn["connection_id"]}
            )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _update_job(document_id, status, error=None):
    item = {
        "job_id": document_id,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if error:
        item["error"] = error
    jobs_table.put_item(Item=item)


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
