"""
DocuMind EC2 Backend — FastAPI application.
Handles all synchronous REST API operations.
OCR and AI processing remain in Lambda (async, SQS-triggered).
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import Depends, FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import verify_token

# ── App & CORS ────────────────────────────────────────────────────────────────
app = FastAPI(title="DocuMind API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── AWS Clients ───────────────────────────────────────────────────────────────
REGION = os.environ["AWS_REGION"]
DOCUMENTS_BUCKET = os.environ["DOCUMENTS_BUCKET"]
DOCUMENTS_TABLE = os.environ["DOCUMENTS_TABLE"]
JOBS_TABLE = os.environ["JOBS_TABLE"]
OCR_QUEUE_URL = os.environ["OCR_QUEUE_URL"]
AI_QUEUE_URL = os.environ["AI_QUEUE_URL"]

s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
sqs = boto3.client("sqs", region_name=REGION)

docs_table = dynamodb.Table(DOCUMENTS_TABLE)
jobs_table = dynamodb.Table(JOBS_TABLE)

ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

# ── Request / Response models ─────────────────────────────────────────────────
class UploadRequest(BaseModel):
    filename: str
    content_type: str

class QARequest(BaseModel):
    question: str

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "documind-ec2-backend"}


# ── POST /documents — request a presigned upload URL ─────────────────────────
@app.post("/documents", status_code=201)
def create_document(body: UploadRequest, claims: dict = Depends(verify_token)):
    if body.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {body.content_type}")

    user_id = claims["sub"]
    document_id = str(uuid.uuid4())
    ext = ALLOWED_CONTENT_TYPES[body.content_type]
    s3_key = f"{user_id}/{document_id}.{ext}"
    now = datetime.now(timezone.utc).isoformat()

    # Generate 15-minute presigned PUT URL
    presigned_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": DOCUMENTS_BUCKET,
            "Key": s3_key,
            "ContentType": body.content_type,
        },
        ExpiresIn=900,
    )

    # Store metadata in DynamoDB
    docs_table.put_item(Item={
        "user_id": user_id,
        "document_id": document_id,
        "filename": body.filename,
        "content_type": body.content_type,
        "s3_key": s3_key,
        "status": "PENDING",
        "created_at": now,
        "updated_at": now,
    })

    return {"document_id": document_id, "upload_url": presigned_url, "s3_key": s3_key}


# ── GET /documents — list user's documents ────────────────────────────────────
@app.get("/documents")
def list_documents(claims: dict = Depends(verify_token)):
    user_id = claims["sub"]
    resp = docs_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(user_id)
    )
    return {"documents": resp.get("Items", [])}


# ── GET /documents/{document_id} — get document metadata ─────────────────────
@app.get("/documents/{document_id}")
def get_document(
    document_id: str = Path(...),
    claims: dict = Depends(verify_token),
):
    user_id = claims["sub"]
    resp = docs_table.get_item(Key={"user_id": user_id, "document_id": document_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")
    return item


# ── DELETE /documents/{document_id} — delete document ────────────────────────
@app.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str = Path(...),
    claims: dict = Depends(verify_token),
):
    user_id = claims["sub"]
    resp = docs_table.get_item(Key={"user_id": user_id, "document_id": document_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from S3
    try:
        s3.delete_object(Bucket=DOCUMENTS_BUCKET, Key=item["s3_key"])
        # Also delete extracted text if it exists
        s3.delete_object(Bucket=DOCUMENTS_BUCKET, Key=item["s3_key"] + ".extracted.txt")
    except ClientError:
        pass  # S3 delete is best-effort

    # Delete from DynamoDB
    docs_table.delete_item(Key={"user_id": user_id, "document_id": document_id})


# ── POST /documents/{document_id}/process — trigger OCR via SQS ──────────────
@app.post("/documents/{document_id}/process", status_code=202)
def process_document(
    document_id: str = Path(...),
    claims: dict = Depends(verify_token),
):
    user_id = claims["sub"]
    resp = docs_table.get_item(Key={"user_id": user_id, "document_id": document_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")
    if item.get("status") not in ("PENDING", "OCR_FAILED"):
        raise HTTPException(status_code=409, detail=f"Document is already in status: {item['status']}")

    now = datetime.now(timezone.utc).isoformat()
    job_id = str(uuid.uuid4())

    # Create job record
    jobs_table.put_item(Item={
        "job_id": job_id,
        "document_id": document_id,
        "user_id": user_id,
        "status": "QUEUED",
        "type": "OCR",
        "created_at": now,
        "expires_at": int(datetime.now(timezone.utc).timestamp()) + 86400,
    })

    # Update document status
    docs_table.update_item(
        Key={"user_id": user_id, "document_id": document_id},
        UpdateExpression="SET #s = :s, job_id = :j, updated_at = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "PROCESSING", ":j": job_id, ":u": now},
    )

    # Enqueue OCR job
    sqs.send_message(
        QueueUrl=OCR_QUEUE_URL,
        MessageBody=json.dumps({
            "job_id": job_id,
            "document_id": document_id,
            "user_id": user_id,
            "s3_key": item["s3_key"],
            "bucket": DOCUMENTS_BUCKET,
            "content_type": item["content_type"],
        }),
    )

    return {"job_id": job_id, "status": "PROCESSING"}


# ── POST /documents/{document_id}/analyze — trigger AI analysis via SQS ───────
@app.post("/documents/{document_id}/analyze", status_code=202)
def analyze_document(
    document_id: str = Path(...),
    claims: dict = Depends(verify_token),
):
    user_id = claims["sub"]
    resp = docs_table.get_item(Key={"user_id": user_id, "document_id": document_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")
    if item.get("status") not in ("OCR_COMPLETE", "AI_FAILED"):
        raise HTTPException(status_code=409, detail=f"Document must be OCR_COMPLETE, current status: {item['status']}")

    now = datetime.now(timezone.utc).isoformat()
    job_id = str(uuid.uuid4())

    jobs_table.put_item(Item={
        "job_id": job_id,
        "document_id": document_id,
        "user_id": user_id,
        "status": "QUEUED",
        "type": "AI",
        "created_at": now,
        "expires_at": int(datetime.now(timezone.utc).timestamp()) + 86400,
    })

    docs_table.update_item(
        Key={"user_id": user_id, "document_id": document_id},
        UpdateExpression="SET #s = :s, job_id = :j, updated_at = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "AI_IN_PROGRESS", ":j": job_id, ":u": now},
    )

    sqs.send_message(
        QueueUrl=AI_QUEUE_URL,
        MessageBody=json.dumps({
            "job_id": job_id,
            "document_id": document_id,
            "user_id": user_id,
            "s3_key": item["s3_key"],
            "bucket": DOCUMENTS_BUCKET,
        }),
    )

    return {"job_id": job_id, "status": "AI_IN_PROGRESS"}


# ── POST /documents/{document_id}/qa — Q&A via AWS Bedrock ────────────────────
@app.post("/documents/{document_id}/qa")
def question_answer(
    body: QARequest,
    document_id: str = Path(...),
    claims: dict = Depends(verify_token),
):
    user_id = claims["sub"]
    resp = docs_table.get_item(Key={"user_id": user_id, "document_id": document_id})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")
    if item.get("status") != "COMPLETE":
        raise HTTPException(status_code=409, detail="Document must be fully processed (COMPLETE) before Q&A")

    # Load extracted text from S3
    extracted_text = ""
    try:
        s3_resp = s3.get_object(Bucket=DOCUMENTS_BUCKET, Key=item["s3_key"] + ".extracted.txt")
        extracted_text = s3_resp["Body"].read().decode("utf-8")[:12000]  # cap at 12KB context
    except ClientError:
        extracted_text = item.get("summary", "No extracted text available.")

    # Call AWS Bedrock (Claude)
    answer = _bedrock_qa(body.question, extracted_text, item.get("filename", "document"))
    return {"question": body.question, "answer": answer, "document_id": document_id}


def _bedrock_qa(question: str, context: str, filename: str) -> str:
    """Call AWS Bedrock Claude for Q&A. Falls back to TF-IDF extract on failure."""
    try:
        bedrock = boto3.client("bedrock-runtime", region_name=REGION)
        prompt = (
            f"You are a document analysis assistant. Answer the question based only on the document content below.\n\n"
            f"Document: {filename}\n\n"
            f"Content:\n{context}\n\n"
            f"Question: {question}\n\n"
            f"Answer concisely and only based on the document content."
        )
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}],
        })
        resp = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=body,
        )
        result = json.loads(resp["body"].read())
        return result["content"][0]["text"]
    except Exception:
        # Fallback: return most relevant sentences using simple TF-IDF
        return _tfidf_extract(question, context)


def _tfidf_extract(query: str, text: str, top_n: int = 3) -> str:
    """Simple extractive answer using sentence-level TF-IDF similarity."""
    import re
    import math

    stop = {"the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and", "or"}

    def tokenize(s: str):
        return [w.lower() for w in re.findall(r"\b[a-z]{3,}\b", s.lower()) if w not in stop]

    sentences = [s.strip() for s in re.split(r"[.!?]", text) if len(s.strip()) > 20]
    if not sentences:
        return "No relevant content found."

    q_tokens = set(tokenize(query))
    scores = []
    for sent in sentences:
        s_tokens = tokenize(sent)
        overlap = len(q_tokens & set(s_tokens))
        scores.append((overlap / (math.log(len(s_tokens) + 1) + 1), sent))

    scores.sort(reverse=True)
    top = [s for _, s in scores[:top_n] if s]
    return " ".join(top) if top else "No relevant content found."


# ── POST /search — keyword search using DynamoDB scan ────────────────────────
@app.post("/search")
def search_documents(body: SearchRequest, claims: dict = Depends(verify_token)):
    user_id = claims["sub"]
    query_lower = body.query.lower()
    limit = min(body.limit or 10, 50)

    # Scan user's documents (DynamoDB — no OpenSearch in Learner Lab)
    resp = docs_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(user_id)
    )
    items = resp.get("Items", [])

    results = []
    for item in items:
        score = 0
        searchable = " ".join(filter(None, [
            item.get("filename", ""),
            item.get("summary", ""),
            " ".join(item.get("keywords", [])),
        ])).lower()
        for word in query_lower.split():
            score += searchable.count(word)
        if score > 0:
            results.append({
                **item,
                "score": score,
                "text": item.get("summary", ""),
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:limit]
    return {"results": top, "count": len(results), "query": body.query}
