variable "project" {
  description = "Prefijo corto del proyecto"
  type        = string
  default     = "static-site"
}

variable "location" {
  description = "Región de Azure"
  type        = string
  default     = "westeurope"
}

variable "resource_group_name" {
  description = "Nombre del Resource Group"
  type        = string
  default     = "rg-static-site-demo"
}

variable "storage_account_name" {
  description = "Nombre ÚNICO para la cuenta de Storage (3-24, solo minúsculas y números)"
  type        = string
  default     = "ststaticsitedemo123"
}

variable "index_document" {
  description = "Documento de inicio del sitio estático"
  type        = string
  default     = "index.html"
}

variable "error_document" {
  description = "Documento 404 del sitio estático"
  type        = string
  default     = "404.html"
}

variable "front_door_sku_name" {
  description = "SKU de Azure Front Door"
  type        = string
  # Valores válidos: "Standard_AzureFrontDoor" | "Premium_AzureFrontDoor"
  default = "Standard_AzureFrontDoor"
}

variable "tags" {
  description = "Etiquetas estándar"
  type        = map(string)
  default = {
    env     = "dev"
    project = "static-site"
    owner   = "demo"
  }
}
