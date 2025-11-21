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
  default = "ststaticsitedemo123" # minúsculas, 3-24, único global
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

variable "tags" {
  type = map(string)
  default = {
    env     = "dev"
    project = "static-site"
    owner   = "demo"
  }
}
