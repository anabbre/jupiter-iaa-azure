variable "project" {
  type    = string
  default = "static-site"
}

variable "location" {
  type    = string
  default = "westeurope"
}

variable "resource_group_name" {
  type    = string
  default = "rg-static-site-demo"
}

variable "storage_account_name" {
  type    = string
  default = "ststaticsitedemo123"
}

variable "index_document" {
  type    = string
  default = "index.html"
}

variable "error_document" {
  type    = string
  default = "404.html"
}

# Front Door Standard/Premium
variable "front_door_sku_name" {
  type    = string
  default = "Standard_AzureFrontDoor"
}

# Log Analytics
variable "log_analytics_workspace_name" {
  type    = string
  default = "law-static-demo"
}

variable "log_analytics_retention_days" {
  type    = number
  default = 30
}

# Alerting
variable "alert_email" {
  type        = string
  description = "Email que recibirá las alertas."
  default     = "alerts@example.com"
}

variable "storage_tx_threshold" {
  type        = number
  description = "Umbral de Transactions en Storage para disparar la alerta."
  default     = 100000
}

variable "afd_total_requests_threshold" {
  type        = number
  description = "Umbral de TotalRequests en Front Door para disparar la alerta."
  default     = 50000
}

variable "tags" {
  type = map(string)
  default = {
    env     = "dev"
    project = "static-site"
    owner   = "demo"
  }
}
