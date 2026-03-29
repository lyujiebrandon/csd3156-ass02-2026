terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

# ── Storage: S3 + DynamoDB ────────────────────────────────────────────────────
module "storage" {
  source       = "./modules/storage"
  project_name = var.project_name
  environment  = var.environment
  account_id   = data.aws_caller_identity.current.account_id
}

# ── Auth: Cognito ─────────────────────────────────────────────────────────────
module "auth" {
  source       = "./modules/auth"
  project_name = var.project_name
  environment  = var.environment
}

# ── Compute: SQS + Lambda (OCR, AI, WebSocket) ───────────────────────────────
# NOTE: Upload and Search logic moved to EC2 FastAPI backend
module "compute" {
  source            = "./modules/compute"
  project_name      = var.project_name
  environment       = var.environment
  documents_bucket  = module.storage.documents_bucket_name
  documents_table   = module.storage.documents_table_name
  jobs_table        = module.storage.jobs_table_name
  connections_table = module.storage.connections_table_name
  aws_region        = var.aws_region
  account_id        = data.aws_caller_identity.current.account_id
}

# ── API: WebSocket only (REST moved to EC2) ───────────────────────────────────
module "api" {
  source               = "./modules/api"
  project_name         = var.project_name
  environment          = var.environment
  websocket_lambda_arn = module.compute.websocket_lambda_arn
}

# ── EC2: FastAPI backend server ───────────────────────────────────────────────
module "ec2" {
  source                = "./modules/ec2"
  project_name          = var.project_name
  environment           = var.environment
  aws_region            = var.aws_region
  documents_bucket      = module.storage.documents_bucket_name
  documents_table       = module.storage.documents_table_name
  jobs_table            = module.storage.jobs_table_name
  connections_table     = module.storage.connections_table_name
  ocr_queue_url         = module.compute.ocr_queue_url
  ai_queue_url          = module.compute.ai_queue_url
  cognito_user_pool_id  = module.auth.user_pool_id
  cognito_client_id     = module.auth.user_pool_client_id
  key_name              = var.key_name
  instance_type         = var.instance_type
}

# ── Monitoring: CloudWatch Alarms + SNS ───────────────────────────────────────
module "monitoring" {
  source           = "./modules/monitoring"
  project_name     = var.project_name
  environment      = var.environment
  alert_email      = var.alert_email
  ec2_instance_id  = module.ec2.instance_id
  ocr_lambda_name  = module.compute.ocr_lambda_name
  ai_lambda_name   = module.compute.ai_lambda_name
  ocr_dlq_name     = module.compute.ocr_dlq_name
  ai_dlq_name      = module.compute.ai_dlq_name
  websocket_api_id = module.api.websocket_api_id
}

# ── OpenSearch: disabled — Academy LabRole lacks es:CreateDomain ──────────────
# ── CloudFront:  disabled — Academy LabRole lacks cloudfront:* permissions ────
# Frontend served via S3 static website (see storage module)
