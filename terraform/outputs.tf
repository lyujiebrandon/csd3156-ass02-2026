output "cloudfront_domain" {
  description = "CloudFront domain for the frontend"
  value       = module.cdn.cloudfront_domain
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

output "opensearch_endpoint" {
  description = "OpenSearch domain endpoint"
  value       = module.search.opensearch_endpoint
}
