import json
import os
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION_NAME"])

OPENSEARCH_ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"]
DOCUMENTS_TABLE = os.environ["DOCUMENTS_TABLE"]
AWS_REGION_NAME = os.environ["AWS_REGION_NAME"]

documents_table = dynamodb.Table(DOCUMENTS_TABLE)

BEDROCK_EMBED_MODEL = "amazon.titan-embed-text-v1"
INDEX_NAME = "documents"


def lambda_handler(event, context):
    user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
    body = json.loads(event.get("body") or "{}")

    query = body.get("query")
    document_id = body.get("document_id")  # optional filter
    search_type = body.get("type", "semantic")  # "semantic" or "keyword"
    limit = min(int(body.get("limit", 10)), 50)

    if not query:
        return _response(400, {"error": "query is required"})

    if search_type == "semantic":
        results = semantic_search(user_id, query, document_id, limit)
    else:
        results = keyword_search(user_id, query, document_id, limit)

    # Enrich with DynamoDB metadata
    enriched = enrich_results(user_id, results)

    return _response(200, {
        "query": query,
        "type": search_type,
        "results": enriched,
        "count": len(enriched),
    })


def semantic_search(user_id, query, document_id, limit):
    """Embed the query and search by vector similarity."""
    embedding = get_embedding(query)
    client = _get_os_client()

    must_filters = [{"term": {"user_id": user_id}}]
    if document_id:
        must_filters.append({"term": {"document_id": document_id}})

    response = client.search(
        index=INDEX_NAME,
        body={
            "size": limit,
            "query": {
                "bool": {
                    "must": must_filters,
                    "should": [{
                        "knn": {
                            "embedding": {"vector": embedding, "k": limit}
                        }
                    }],
                }
            },
            "_source": {"excludes": ["embedding"]},
        },
    )

    return [
        {
            "document_id": hit["_source"]["document_id"],
            "chunk_id": hit["_source"]["chunk_id"],
            "text": hit["_source"]["text"],
            "score": hit["_score"],
        }
        for hit in response["hits"]["hits"]
    ]


def keyword_search(user_id, query, document_id, limit):
    """Full-text keyword search using OpenSearch BM25."""
    client = _get_os_client()

    must_filters = [{"term": {"user_id": user_id}}]
    if document_id:
        must_filters.append({"term": {"document_id": document_id}})

    response = client.search(
        index=INDEX_NAME,
        body={
            "size": limit,
            "query": {
                "bool": {
                    "must": must_filters + [{"match": {"text": query}}]
                }
            },
            "_source": {"excludes": ["embedding"]},
        },
    )

    return [
        {
            "document_id": hit["_source"]["document_id"],
            "chunk_id": hit["_source"]["chunk_id"],
            "text": hit["_source"]["text"],
            "score": hit["_score"],
        }
        for hit in response["hits"]["hits"]
    ]


def enrich_results(user_id, results):
    """Add document filename and status from DynamoDB."""
    seen_docs = {}
    enriched = []

    for result in results:
        doc_id = result["document_id"]
        if doc_id not in seen_docs:
            item = documents_table.get_item(
                Key={"user_id": user_id, "document_id": doc_id}
            ).get("Item", {})
            seen_docs[doc_id] = {
                "filename": item.get("filename", "Unknown"),
                "status": item.get("status", "Unknown"),
                "created_at": item.get("created_at", ""),
            }

        enriched.append({**result, **seen_docs[doc_id]})

    return enriched


def get_embedding(text):
    body = json.dumps({"inputText": text[:8000]})
    response = bedrock.invoke_model(modelId=BEDROCK_EMBED_MODEL, body=body)
    result = json.loads(response["body"].read())
    return result["embedding"]


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


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
