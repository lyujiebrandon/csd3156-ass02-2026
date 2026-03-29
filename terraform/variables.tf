variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name prefix for all resources"
  type        = string
  default     = "documind-group20"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

variable "key_name" {
  description = "EC2 SSH key pair name — use 'vockey' for AWS Academy Learner Lab"
  type        = string
  default     = "vockey"
}

variable "instance_type" {
  description = "EC2 instance type for the backend server"
  type        = string
  default     = "t3.micro"
}

variable "alert_email" {
  description = "Email address to receive CloudWatch alarm notifications"
  type        = string
  default     = "brandonlyj@hotmail.com"
}
