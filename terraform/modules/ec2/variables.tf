variable "project_name"      { type = string }
variable "environment"       { type = string }
variable "aws_region"        { type = string }
variable "documents_bucket"  { type = string }
variable "documents_table"   { type = string }
variable "jobs_table"        { type = string }
variable "connections_table" { type = string }
variable "ocr_queue_url"     { type = string }
variable "ai_queue_url"      { type = string }
variable "cognito_user_pool_id"  { type = string }
variable "cognito_client_id"    { type = string }

variable "key_name" {
  description = "EC2 key pair name (use 'vockey' for AWS Academy Learner Lab)"
  type        = string
  default     = "vockey"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}
