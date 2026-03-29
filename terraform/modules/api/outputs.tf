output "websocket_url" {
  value       = aws_apigatewayv2_stage.websocket.invoke_url
  description = "WebSocket URL for real-time notifications (wss://...)"
}

output "websocket_api_id" {
  value = aws_apigatewayv2_api.websocket.id
}
