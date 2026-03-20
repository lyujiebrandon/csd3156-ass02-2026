output "documents_bucket_name" {
  value = aws_s3_bucket.documents.bucket
}

output "documents_bucket_arn" {
  value = aws_s3_bucket.documents.arn
}

output "frontend_bucket_id" {
  value = aws_s3_bucket.frontend.id
}

output "frontend_bucket_arn" {
  value = aws_s3_bucket.frontend.arn
}

output "frontend_website_url" {
  value = aws_s3_bucket_website_configuration.frontend.website_endpoint
}

output "documents_table_name" {
  value = aws_dynamodb_table.documents.name
}

output "jobs_table_name" {
  value = aws_dynamodb_table.jobs.name
}

output "connections_table_name" {
  value = aws_dynamodb_table.connections.name
}
