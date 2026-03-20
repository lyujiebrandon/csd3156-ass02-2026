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

module "storage" {
  source       = "./modules/storage"
  project_name = var.project_name
  environment  = var.environment
  account_id   = data.aws_caller_identity.current.account_id
}

module "auth" {
  source       = "./modules/auth"
  project_name = var.project_name
  environment  = var.environment
}

module "compute" {
  source              = "./modules/compute"
  project_name        = var.project_name
  environment         = var.environment
  documents_bucket    = module.storage.documents_bucket_name
  documents_table     = module.storage.documents_table_name
  jobs_table          = module.storage.jobs_table_name
  connections_table   = module.storage.connections_table_name
  opensearch_endpoint = ""
  aws_region          = var.aws_region
  account_id          = data.aws_caller_identity.current.account_id
}

module "api" {
  source               = "./modules/api"
  project_name         = var.project_name
  environment          = var.environment
  aws_region           = var.aws_region
  account_id           = data.aws_caller_identity.current.account_id
  cognito_user_pool_arn = module.auth.user_pool_arn
  upload_lambda_arn    = module.compute.upload_lambda_arn
  ai_lambda_arn        = module.compute.ai_lambda_arn
  search_lambda_arn    = module.compute.search_lambda_arn
  websocket_lambda_arn = module.compute.websocket_lambda_arn
}

# module "search" disabled — Academy LabRole lacks es:CreateDomain permission
# module "cdn"    disabled — Academy LabRole lacks cloudfront:* permissions
# Frontend is served via S3 static website (see storage module)
