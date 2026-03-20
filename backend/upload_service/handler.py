import json
import os
import uuid
import boto3
from datetime import datetime, timezone

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

DOCUMENTS_BUCKET = os.environ["DOCUMENTS_BUCKET"]
DOCUMENTS_TABLE = os.environ["DOCUMENTS_TABLE"]
OCR_QUEUE_URL = os.environ["OCR_QUEUE_URL"]

sqs = boto3.client("sqs")
table = dynamodb.Table(DOCUMENTS_TABLE)

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def _get_user_id(event):
    return event["requestContext"]["authorizer"]["claims"]["sub"]


def lambda_handler(event, context):
    method = event["httpMethod"]
    path = event.get("path", "")

    if method == "POST" and path.endswith("/documents"):
        return handle_create_upload(event)
    elif method == "GET" and path.endswith("/documents"):
        return handle_list_documents(event)
    elif method == "POST" and "/process" in path:
        return handle_start_processing(event)
    else:
        return _response(404, {"error": "Not found"})


def handle_create_upload(event):
    """Generate a presigned S3 URL and create a DynamoDB record."""
    user_id = _get_user_id(event)
    body = json.loads(event.get("body") or "{}")

    filename = body.get("filename")
    content_type = body.get("content_type")

    if not filename or not content_type:
        return _response(400, {"error": "filename and content_type are required"})

    if content_type not in ALLOWED_TYPES:
        return _response(400, {"error": f"Unsupported file type: {content_type}"})

    document_id = str(uuid.uuid4())
    s3_key = f"{user_id}/{document_id}/{filename}"

    # Generate presigned URL (15 minute expiry)
    presigned_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": DOCUMENTS_BUCKET,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=900,
    )

    # Save document metadata
    now = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        "user_id": user_id,
        "document_id": document_id,
        "filename": filename,
        "content_type": content_type,
        "s3_key": s3_key,
        "status": "PENDING",
        "created_at": now,
        "updated_at": now,
    })

    return _response(201, {
        "document_id": document_id,
        "upload_url": presigned_url,
        "s3_key": s3_key,
    })


def handle_list_documents(event):
    """List all documents for the authenticated user."""
    user_id = _get_user_id(event)

    result = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(user_id)
    )

    return _response(200, {"documents": result.get("Items", [])})


def handle_start_processing(event):
    """Called by frontend after file upload completes — queues the OCR job."""
    user_id = _get_user_id(event)
    document_id = event["pathParameters"]["document_id"]

    # Fetch the document to get s3_key
    result = table.get_item(Key={"user_id": user_id, "document_id": document_id})
    item = result.get("Item")

    if not item:
        return _response(404, {"error": "Document not found"})

    if item["status"] != "PENDING":
        return _response(409, {"error": f"Document already in status: {item['status']}"})

    # Update status to PROCESSING
    table.update_item(
        Key={"user_id": user_id, "document_id": document_id},
        UpdateExpression="SET #s = :s, updated_at = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "PROCESSING",
            ":u": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Send to OCR queue
    sqs.send_message(
        QueueUrl=OCR_QUEUE_URL,
        MessageBody=json.dumps({
            "user_id": user_id,
            "document_id": document_id,
            "s3_key": item["s3_key"],
            "content_type": item["content_type"],
        }),
    )

    return _response(202, {"message": "Processing started", "document_id": document_id})
