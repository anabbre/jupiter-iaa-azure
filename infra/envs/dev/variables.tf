variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "eu-west-1"
}

variable "prefix" {
  type        = string
  description = "Resource name prefix"
  default     = "jupiter-iaa"
}

variable "environment" {
  type        = string
  description = "Environment name"
  default     = "dev"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block"
  default     = "10.20.0.0/16"
}

variable "az_count" {
  type        = number
  description = "Number of AZs to use"
  default     = 2
}

variable "openai_api_key" {
  type      = string
  sensitive = true
}

variable "uploads_index_name" { type = string }
variable "kb_index_name" { type = string }
