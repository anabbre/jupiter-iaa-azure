variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "tags" {
  type = map(string)
}

# ECR image URIs (ya los tienes por output)
variable "api_image" {
  type        = string
  description = "ECR image URI for API (e.g. <acct>.dkr.ecr.../jupiter-iaa-dev-api:dev)"
}

variable "ui_image" {
  type        = string
  description = "ECR image URI for UI (e.g. <acct>.dkr.ecr.../jupiter-iaa-dev-ui:dev)"
}

# ALB
variable "alb_listener_http_arn" {
  type = string
}

variable "alb_sg_id" {
  type = string
}

# Ports
variable "api_port" {
  type    = number
  default = 8008
}

variable "ui_port" {
  type    = number
  default = 7860
}

variable "qdrant_port" {
  type    = number
  default = 6333
}

# Qdrant + EFS
variable "efs_id" {
  type = string
}

variable "efs_access_point_id" {
  type = string
}

variable "efs_sg_id" {
  type = string
}

# App env
variable "openai_api_key" {
  type      = string
  sensitive = true
}

variable "log_level" {
  type    = string
  default = "INFO"
}

# Qdrant collection/index names
variable "uploads_index_name" {
  type = string
}

variable "kb_index_name" {
  type = string
}

variable "alb_dns_name" {
  type        = string
  description = "DNS name del ALB (sin http/https)"
}
