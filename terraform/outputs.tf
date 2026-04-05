output "ec2_public_ip" {
  description = "Public IP of the EC2 backend server"
  value       = module.ec2.public_ip
}

output "api_url" {
  description = "REST API base URL (EC2 Nginx on port 80)"
  value       = module.ec2.api_url
}

output "websocket_url" {
  description = "WebSocket API URL for real-time notifications"
  value       = module.api.websocket_url
}

output "frontend_url" {
  description = "S3 static website URL for the frontend"
  value       = "http://${module.storage.frontend_website_url}"
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.auth.user_pool_id
}

output "cognito_client_id" {
  description = "Cognito App Client ID"
  value       = module.auth.user_pool_client_id
}

output "documents_bucket" {
  description = "S3 bucket for document storage"
  value       = module.storage.documents_bucket_name
}

output "frontend_bucket" {
  description = "S3 bucket name for the frontend static website"
  value       = module.storage.frontend_bucket_id
}

output "cloudwatch_dashboard_url" {
  description = "URL to the CloudWatch monitoring dashboard"
  value       = module.monitoring.dashboard_url
}

output "sns_alerts_topic_arn" {
  description = "SNS topic ARN for CloudWatch alerts"
  value       = module.monitoring.sns_topic_arn
}
