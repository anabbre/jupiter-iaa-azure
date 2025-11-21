variable "project" {
  description = "Nombre corto del proyecto para etiquetar recursos"
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
  description = "Nombre único para la cuenta de Storage (minúsculas, 3–24, solo letras y números)"
  type        = string
  default     = "ststaticsitedemo123"
}

variable "index_document" {
  description = "Documento de inicio para static website"
  type        = string
  default     = "index.html"
}

variable "error_document" {
  description = "Documento de error para static website"
  type        = string
  default     = "404.html"
}

# CDN
variable "cdn_sku" {
  description = "SKU del CDN clásico"
  type        = string
  default     = "Standard_Microsoft"
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
