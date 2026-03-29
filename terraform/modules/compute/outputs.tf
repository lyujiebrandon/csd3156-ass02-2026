output "ocr_lambda_arn" {
  value = aws_lambda_function.ocr.arn
}

output "ocr_lambda_name" {
  value = aws_lambda_function.ocr.function_name
}

output "ai_lambda_arn" {
  value = aws_lambda_function.ai.arn
}

output "ai_lambda_name" {
  value = aws_lambda_function.ai.function_name
}

output "websocket_lambda_arn" {
  value = aws_lambda_function.websocket.arn
}

output "ocr_queue_url" {
  value = aws_sqs_queue.ocr.url
}

output "ocr_queue_arn" {
  value = aws_sqs_queue.ocr.arn
}

output "ai_queue_url" {
  value = aws_sqs_queue.ai.url
}

output "ocr_dlq_name" {
  value = aws_sqs_queue.ocr_dlq.name
}

output "ai_dlq_name" {
  value = aws_sqs_queue.ai_dlq.name
}
