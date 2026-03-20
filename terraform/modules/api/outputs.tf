output "rest_api_url" {
  value = "${aws_api_gateway_stage.prod.invoke_url}"
}

output "websocket_url" {
  value = "${aws_apigatewayv2_stage.websocket.invoke_url}"
}
