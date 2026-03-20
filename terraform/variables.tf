variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "ap-southeast-1"
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
