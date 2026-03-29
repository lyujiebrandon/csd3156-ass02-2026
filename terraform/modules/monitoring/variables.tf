variable "project_name"    { type = string }
variable "environment"     { type = string }
variable "ec2_instance_id" { type = string }
variable "ocr_lambda_name" { type = string }
variable "ai_lambda_name"  { type = string }
variable "ocr_dlq_name"    { type = string }
variable "ai_dlq_name"     { type = string }

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
}

variable "websocket_api_id" {
  type    = string
  default = ""
}
