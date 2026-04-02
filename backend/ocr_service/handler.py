import json
import os
import boto3
from datetime import datetime, timezone

s3 = boto3.client("s3")
textract = boto3.client("textract")
dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

DOCUMENTS_BUCKET = os.environ["DOCUMENTS_BUCKET"]
JOBS_TABLE = os.environ["JOBS_TABLE"]
AI_QUEUE_URL = os.environ["AI_QUEUE_URL"]
AWS_REGION_NAME = os.environ["AWS_REGION_NAME"]

jobs_table = dynamodb.Table(JOBS_TABLE)


def lambda_handler(event, context):
    for record in event["Records"]:
        message = json.loads(record["body"])
        process_document(message)


def process_document(message):
    user_id = message["user_id"]
    document_id = message["document_id"]
    s3_key = message["s3_key"]
    content_type = message["content_type"]

    # Update job status
    _update_job(document_id, "OCR_IN_PROGRESS")

    try:
        extracted_text = extract_text(s3_key, content_type)

        # Save extracted text back to S3 (avoids DynamoDB 400KB limit)
        text_key = f"{s3_key}.extracted.txt"
        s3.put_object(
            Bucket=DOCUMENTS_BUCKET,
            Key=text_key,
            Body=extracted_text.encode("utf-8"),
            ContentType="text/plain",
        )

        _update_job(document_id, "OCR_COMPLETE")

        # Forward to AI queue
        sqs.send_message(
            QueueUrl=AI_QUEUE_URL,
            MessageBody=json.dumps({
                "user_id": user_id,
                "document_id": document_id,
                "s3_key": s3_key,
                "text_key": text_key,
                "char_count": len(extracted_text),
            }),
        )

    except Exception as e:
        _update_job(document_id, "OCR_FAILED", error=str(e))
        raise  # Re-raise so SQS retries / DLQ catches it


def extract_text(s3_key, content_type):
    """Use Textract to extract text. Sync for images, async for PDFs."""
    if content_type == "application/pdf":
        return _extract_pdf(s3_key)
    else:
        return _extract_image(s3_key)


def _extract_image(s3_key):
    """Synchronous Textract for images (JPEG/PNG)."""
    response = textract.detect_document_text(
        Document={"S3Object": {"Bucket": DOCUMENTS_BUCKET, "Name": s3_key}}
    )
    return _parse_blocks(response["Blocks"])


def _extract_pdf(s3_key):
    """Asynchronous Textract for PDFs — waits for completion."""
    import time

    response = textract.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": DOCUMENTS_BUCKET, "Name": s3_key}}
    )
    job_id = response["JobId"]

    # Poll until complete — bail out after 240s so Lambda can fail cleanly
    deadline = time.time() + 240
    while time.time() < deadline:
        result = textract.get_document_text_detection(JobId=job_id)
        status = result["JobStatus"]

        if status == "SUCCEEDED":
            blocks = result["Blocks"]
            while "NextToken" in result:
                result = textract.get_document_text_detection(
                    JobId=job_id, NextToken=result["NextToken"]
                )
                blocks.extend(result["Blocks"])
            return _parse_blocks(blocks)

        elif status == "FAILED":
            raise RuntimeError(f"Textract job {job_id} failed")

        time.sleep(5)

    raise RuntimeError(f"Textract job {job_id} timed out after 240s")


def _parse_blocks(blocks):
    """Extract LINE-level text from Textract blocks."""
    lines = [
        block["Text"]
        for block in blocks
        if block["BlockType"] == "LINE"
    ]
    return "\n".join(lines)


def _update_job(document_id, status, error=None):
    item = {
        "job_id": document_id,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if error:
        item["error"] = error

    jobs_table.put_item(Item=item)
