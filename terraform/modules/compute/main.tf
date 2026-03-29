# ── SQS Queues ────────────────────────────────────────────────────────────────
resource "aws_sqs_queue" "ocr_dlq" {
  name = "${var.project_name}-ocr-dlq"
  tags = { Environment = var.environment }
}

resource "aws_sqs_queue" "ocr" {
  name                       = "${var.project_name}-ocr-queue"
  visibility_timeout_seconds = 300
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ocr_dlq.arn
    maxReceiveCount     = 3
  })
  tags = { Environment = var.environment }
}

resource "aws_sqs_queue" "ai_dlq" {
  name = "${var.project_name}-ai-dlq"
  tags = { Environment = var.environment }
}

resource "aws_sqs_queue" "ai" {
  name                       = "${var.project_name}-ai-queue"
  visibility_timeout_seconds = 300
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ai_dlq.arn
    maxReceiveCount     = 3
  })
  tags = { Environment = var.environment }
}

# ── IAM Role for Lambda (use Academy LabRole — cannot create roles in Learner Lab) ──
data "aws_iam_role" "lambda_exec" {
  name = "LabRole"
}

# ── Lambda: OCR Service (async, triggered by SQS) ─────────────────────────────
data "archive_file" "ocr" {
  type        = "zip"
  source_dir  = "${path.root}/../backend/ocr_service"
  output_path = "${path.module}/zips/ocr_service.zip"
}

resource "aws_lambda_function" "ocr" {
  filename         = data.archive_file.ocr.output_path
  function_name    = "${var.project_name}-ocr-service"
  role             = data.aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.ocr.output_base64sha256
  timeout          = 300
  tracing_config { mode = "Active" }

  environment {
    variables = {
      DOCUMENTS_BUCKET = var.documents_bucket
      DOCUMENTS_TABLE  = var.documents_table
      JOBS_TABLE       = var.jobs_table
      AI_QUEUE_URL     = aws_sqs_queue.ai.url
      AWS_REGION_NAME  = var.aws_region
    }
  }

  tags = { Environment = var.environment }
}

resource "aws_lambda_event_source_mapping" "ocr_trigger" {
  event_source_arn = aws_sqs_queue.ocr.arn
  function_name    = aws_lambda_function.ocr.arn
  batch_size       = 1
}

# ── Lambda: AI Analysis Service (async, triggered by SQS) ─────────────────────
data "archive_file" "ai" {
  type        = "zip"
  source_dir  = "${path.root}/../backend/ai_service"
  output_path = "${path.module}/zips/ai_service.zip"
}

resource "aws_lambda_function" "ai" {
  filename         = data.archive_file.ai.output_path
  function_name    = "${var.project_name}-ai-service"
  role             = data.aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.ai.output_base64sha256
  timeout          = 300
  tracing_config { mode = "Active" }

  environment {
    variables = {
      DOCUMENTS_BUCKET  = var.documents_bucket
      DOCUMENTS_TABLE   = var.documents_table
      JOBS_TABLE        = var.jobs_table
      CONNECTIONS_TABLE = var.connections_table
      AWS_REGION_NAME   = var.aws_region
      BEDROCK_REGION    = var.aws_region
    }
  }

  tags = { Environment = var.environment }
}

resource "aws_lambda_event_source_mapping" "ai_trigger" {
  event_source_arn = aws_sqs_queue.ai.arn
  function_name    = aws_lambda_function.ai.arn
  batch_size       = 1
}

# ── Lambda: WebSocket Handler ─────────────────────────────────────────────────
data "archive_file" "websocket" {
  type        = "zip"
  source_dir  = "${path.root}/../backend/websocket_handler"
  output_path = "${path.module}/zips/websocket_handler.zip"
}

resource "aws_lambda_function" "websocket" {
  filename         = data.archive_file.websocket.output_path
  function_name    = "${var.project_name}-websocket-handler"
  role             = data.aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.websocket.output_base64sha256
  timeout          = 30
  tracing_config { mode = "Active" }

  environment {
    variables = {
      CONNECTIONS_TABLE = var.connections_table
      AWS_REGION_NAME   = var.aws_region
    }
  }

  tags = { Environment = var.environment }
}
