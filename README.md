# DocuMind — Cloud-Native AI Document Intelligence Platform

CSD3156 Cloud Computing | Group 20 | SIT 2025/2026 T2

---

## Overview

DocuMind is a cloud-native platform for AI-powered document intelligence built on AWS.
Users upload documents (PDF, JPEG, PNG, DOC, DOCX) and receive:

- **OCR extraction** via AWS Textract
- **AI summaries and keyword analysis** via AWS Bedrock (Claude)
- **Semantic Q&A** over document content
- **Real-time processing status** via WebSocket

---

## Architecture

```
Browser (S3 Static Website)
    │
    ├── Auth ──────────────► AWS Cognito (User Pool)
    │
    ├── REST API ──────────► EC2 (FastAPI + Nginx)
    │                            │
    │                            ├── DynamoDB (document metadata, jobs)
    │                            ├── S3 (document storage)
    │                            └── SQS (OCR + AI job queues)
    │
    ├── WebSocket ─────────► API Gateway (WebSocket) → Lambda
    │
    └── File Upload ───────► S3 (presigned URL, direct browser upload)

SQS Triggers:
    OCR Queue  → Lambda (ocr_service)  → Textract → S3
    AI Queue   → Lambda (ai_service)   → Bedrock  → DynamoDB
```

---

## Project Structure

```
setup.bat                   # First-time deployment script
refresh-env.bat             # Run at the start of each Learner Lab session
deploy-ec2.bat              # Push backend code changes to a running EC2
DEPLOYMENT.md               # Full deployment guide

terraform/                  # AWS infrastructure as code (Terraform)
  modules/
    auth/                   # Cognito User Pool + App Client
    compute/                # Lambda functions + SQS queues
    ec2/                    # EC2 instance + security group + Nginx
    api/                    # API Gateway WebSocket
    storage/                # S3 buckets + DynamoDB tables
    monitoring/             # CloudWatch dashboards + SNS alerts

backend/
  ec2_app/                  # FastAPI application (runs on EC2)
    main.py                 # REST API endpoints
    auth.py                 # Cognito JWT verification
    requirements.txt
  lambdas/
    ocr_service/            # Textract OCR processing (SQS-triggered)
    ai_service/             # Bedrock AI analysis (SQS-triggered)
    websocket_handler/      # WebSocket connect/disconnect/message

frontend/                   # React SPA (deployed to S3)
  src/
    pages/                  # Dashboard, Upload, Search, Login, Signup
    services/               # API, Auth, WebSocket clients
    components/
```

---

## Quick Start

> For full instructions see **[DEPLOYMENT.md](DEPLOYMENT.md)**

### Prerequisites
- [Terraform](https://developer.hashicorp.com/terraform/downloads)
- [Node.js + npm](https://nodejs.org)
- [AWS CLI](https://aws.amazon.com/cli)

### First-time deployment

1. Start your AWS Academy Learner Lab session and update `%USERPROFILE%\.aws\credentials`
2. Double-click **`setup.bat`** — deploys all infrastructure, type `yes` when prompted
3. Double-click **`refresh-env.bat`** — builds the React app and deploys it to S3
4. Open the Frontend URL printed at the end of `refresh-env.bat`

### Each new Learner Lab session

1. Update `%USERPROFILE%\.aws\credentials` with new session credentials
2. Run **`refresh-env.bat`**

### Tear down

```
cd terraform
terraform destroy
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `setup.bat` | First-time deployment — provisions all AWS infrastructure |
| `refresh-env.bat` | Updates `.env.local`, rebuilds frontend, and redeploys to S3 |
| `deploy-ec2.bat` | Pushes backend code changes to a running EC2 (no SSH needed) |
