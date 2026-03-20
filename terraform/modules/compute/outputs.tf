output "upload_lambda_arn" {
  value = aws_lambda_function.upload.arn
}

output "ocr_lambda_arn" {
  value = aws_lambda_function.ocr.arn
}

output "ai_lambda_arn" {
  value = aws_lambda_function.ai.arn
}

output "search_lambda_arn" {
  value = aws_lambda_function.search.arn
}

output "websocket_lambda_arn" {
  value = aws_lambda_function.websocket.arn
}

output "ocr_queue_url" {
  value = aws_sqs_queue.ocr.url
}

output "ai_queue_url" {
  value = aws_sqs_queue.ai.url
}
