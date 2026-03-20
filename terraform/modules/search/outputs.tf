output "opensearch_endpoint" {
  value = aws_opensearch_domain.main.endpoint
}

output "opensearch_arn" {
  value = aws_opensearch_domain.main.arn
}
