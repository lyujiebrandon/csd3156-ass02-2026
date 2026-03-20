# DocuMind — Cloud-Native AI Document Intelligence Platform

CSD3156 Cloud Computing | Group 20 | SIT 2025/2026 T2

## Overview
DocuMind is a fully serverless, event-driven platform for AI-powered document intelligence.
Users upload documents and receive OCR extraction, AI summaries, keyword analysis, and can perform semantic Q&A over their documents using RAG.

## Architecture
- **Frontend:** React.js → S3 + CloudFront
- **Auth:** AWS Cognito
- **API:** AWS API Gateway (REST + WebSocket)
- **Compute:** AWS Lambda (Python)
- **AI:** AWS Bedrock (LLM) + AWS Textract (OCR)
- **Storage:** S3 (documents), DynamoDB (metadata), OpenSearch (vectors)
- **Messaging:** SQS
- **IaC:** Terraform
- **CI/CD:** GitHub Actions

## Project Structure
```
terraform/          # AWS infrastructure (Terraform)
backend/            # Lambda functions (Python)
  upload_service/   # Presigned URL generation
  ocr_service/      # Textract OCR processing
  ai_service/       # Bedrock AI analysis + RAG
  search_service/   # OpenSearch semantic search
  websocket_handler/# Real-time WebSocket notifications
frontend/           # React.js SPA
.github/workflows/  # CI/CD pipelines
docs/               # Project documentation
```

## Setup
See individual README files in each subdirectory.
