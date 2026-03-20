output "frontend_url" {
  description = "S3 static website URL for the frontend"
  value       = "http://${module.storage.frontend_website_url}"
}

output "api_gateway_url" {
  description = "REST API Gateway invoke URL"
  value       = module.api.rest_api_url
}

output "websocket_url" {
  description = "WebSocket API Gateway URL"
  value       = module.api.websocket_url
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

# opensearch_endpoint output removed — OpenSearch disabled in Academy Learner Lab
