import json
import os
import boto3
from datetime import datetime, timezone

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

DOCUMENTS_TABLE = os.environ["DOCUMENTS_TABLE"]
JOBS_TABLE = os.environ["JOBS_TABLE"]
CONNECTIONS_TABLE = os.environ["CONNECTIONS_TABLE"]
DOCUMENTS_BUCKET = os.environ["DOCUMENTS_BUCKET"]
AWS_REGION_NAME = os.environ["AWS_REGION_NAME"]

documents_table = dynamodb.Table(DOCUMENTS_TABLE)
jobs_table = dynamodb.Table(JOBS_TABLE)
connections_table = dynamodb.Table(CONNECTIONS_TABLE)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = "claude-3-haiku-20240307"


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


# ── AI: Try Bedrock, fall back to local NLP ───────────────────────────────────

def generate_summary(text):
    """Try Bedrock Claude first; fall back to TextRank extractive summary."""
    try:
        return _invoke_claude(
            "You are a document analysis assistant. "
            "Provide a concise summary (3-5 sentences) of the following document:\n\n"
            f"{text[:8000]}"
        )
    except Exception:
        return _textrank_summary(text, num_sentences=5)


def extract_keywords(text):
    """Try Bedrock Claude first; fall back to TF-IDF keyword extraction."""
    try:
        response = _invoke_claude(
            "Extract 10 key topics or keywords from the following document. "
            "Return them as a JSON array of strings, e.g. [\"keyword1\", \"keyword2\"]. "
            "Return ONLY the JSON array, no other text.\n\n"
            f"{text[:4000]}"
        )
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return [k.strip().strip('"') for k in response.strip("[]").split(",")]
    except Exception:
        return _tfidf_keywords(text, top_n=10)


def _invoke_claude(prompt):
    """Call Anthropic API directly via urllib — no AWS permissions needed."""
    import urllib.request
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    payload = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    return result["content"][0]["text"]


# ── NLP Utilities (pure Python stdlib) ───────────────────────────────────────

import re
import math
from collections import Counter

STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "is","are","was","were","be","been","being","have","has","had","do",
    "does","did","will","would","could","should","may","might","shall",
    "that","this","these","those","it","its","by","from","as","into",
    "not","no","so","if","then","than","when","where","which","who",
    "their","they","we","our","your","my","his","her","all","each",
    "any","both","few","more","most","other","some","such","up","out",
    "about","also","can","just","after","before","between","through",
    "during","since","while","although","however","therefore","thus",
    "i","you","he","she","we","they","me","him","us","them",
}


def _tokenize(text):
    return [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text) if w.lower() not in STOPWORDS]


def _split_sentences(text):
    raw = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in raw if len(s.split()) >= 6]


def _tfidf_vectors(sentences):
    """Compute TF-IDF vector (as Counter) for each sentence."""
    tokenized = [_tokenize(s) for s in sentences]
    n = len(sentences)
    # Document frequency
    df = Counter()
    for tokens in tokenized:
        for w in set(tokens):
            df[w] += 1
    # IDF
    idf = {w: math.log((n + 1) / (freq + 1)) + 1 for w, freq in df.items()}
    # TF-IDF vectors
    vectors = []
    for tokens in tokenized:
        tf = Counter(tokens)
        total = len(tokens) or 1
        vec = {w: (count / total) * idf.get(w, 1) for w, count in tf.items()}
        vectors.append(vec)
    return vectors


def _cosine_similarity(v1, v2):
    common = set(v1) & set(v2)
    if not common:
        return 0.0
    dot = sum(v1[w] * v2[w] for w in common)
    mag1 = math.sqrt(sum(x * x for x in v1.values()))
    mag2 = math.sqrt(sum(x * x for x in v2.values()))
    return dot / (mag1 * mag2) if mag1 and mag2 else 0.0


def _textrank_summary(text, num_sentences=5):
    """
    TextRank: rank sentences by graph-based importance (similar to PageRank).
    Returns the top-ranked sentences in their original document order.
    """
    sentences = _split_sentences(text)
    if len(sentences) <= num_sentences:
        return " ".join(sentences)

    vectors = _tfidf_vectors(sentences)
    n = len(sentences)

    # Build similarity matrix
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                sim[i][j] = _cosine_similarity(vectors[i], vectors[j])

    # PageRank iteration
    damping = 0.85
    scores = [1.0 / n] * n
    for _ in range(30):
        new_scores = [(1 - damping) / n] * n
        for i in range(n):
            col_sum = sum(sim[k][i] for k in range(n))
            if col_sum == 0:
                continue
            for j in range(n):
                if sim[j][i] > 0:
                    new_scores[j] += damping * scores[i] * (sim[j][i] / col_sum)
        scores = new_scores

    # Pick top sentences, restore original order
    ranked = sorted(range(n), key=lambda i: scores[i], reverse=True)
    top_indices = sorted(ranked[:num_sentences])
    return " ".join(sentences[i] for i in top_indices)


def _tfidf_keywords(text, top_n=10):
    """
    TF-IDF keyword extraction: score each unique word by its TF-IDF weight
    across document paragraphs, favouring content-specific terms.
    """
    paragraphs = [p.strip() for p in re.split(r'\n+', text) if len(p.strip()) > 30]
    if not paragraphs:
        paragraphs = [text]

    vectors = _tfidf_vectors(paragraphs)
    # Sum TF-IDF scores across all paragraphs
    global_scores = Counter()
    for vec in vectors:
        for word, score in vec.items():
            global_scores[word] += score

    # Prefer longer words (more specific) with a slight length bonus
    adjusted = {w: s * (1 + 0.05 * len(w)) for w, s in global_scores.items()}
    top = sorted(adjusted, key=adjusted.get, reverse=True)
    return top[:top_n]


def _tfidf_answer(question, context_text, top_k=5):
    """
    TF-IDF sentence retrieval for Q&A: find the sentences most similar
    to the question, then compose a coherent answer.
    """
    sentences = _split_sentences(context_text)
    if not sentences:
        return "I could not find relevant content in the document."

    all_texts = sentences + [question]
    vectors = _tfidf_vectors(all_texts)
    q_vec = vectors[-1]
    sent_vecs = vectors[:-1]

    scored = [(i, _cosine_similarity(q_vec, sv)) for i, sv in enumerate(sent_vecs)]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Take top_k relevant sentences, restore order for readability
    top_indices = sorted([i for i, score in scored[:top_k] if score > 0])
    if not top_indices:
        return "I could not find a relevant answer in the document."

    answer_sentences = [sentences[i] for i in top_indices]
    return "Based on the document: " + " ".join(answer_sentences)


# ── Q&A (RAG) ─────────────────────────────────────────────────────────────────

def handle_qa_request(event):
    user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
    body = json.loads(event.get("body") or "{}")
    question = body.get("question")
    document_id = body.get("document_id")

    if not question:
        return _response(400, {"error": "question is required"})

    if not document_id:
        return _response(400, {"error": "document_id is required"})

    # Load document summary and text for context
    result = documents_table.get_item(
        Key={"user_id": user_id, "document_id": document_id}
    )
    item = result.get("Item")

    if not item:
        return _response(404, {"error": "Document not found"})

    if item.get("status") != "COMPLETE":
        return _response(400, {"error": "Document is still processing"})

    # Use summary + extracted text as context
    context = item.get("summary", "")
    text_key = item.get("s3_key", "") + ".extracted.txt"
    try:
        obj = s3.get_object(Bucket=DOCUMENTS_BUCKET, Key=text_key)
        full_text = obj["Body"].read().decode("utf-8")
        context = full_text[:12000]  # Use first 12k chars as context
    except Exception:
        context = item.get("summary", "No content available")

    prompt = (
        "You are a helpful document assistant. "
        "Answer the user's question using ONLY the context below. "
        "If the answer is not in the context, say 'I could not find this in the documents'.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )

    try:
        answer = _invoke_claude(prompt)
    except Exception:
        answer = _tfidf_answer(question, context)

    return _response(200, {
        "answer": answer,
        "sources": [{"document_id": document_id}],
    })


# ── WebSocket Notifications ────────────────────────────────────────────────────

def notify_user(user_id, payload):
    result = connections_table.query(
        IndexName="user_id-index",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(user_id),
    )

    if not result.get("Items"):
        return

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
        except Exception:
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
