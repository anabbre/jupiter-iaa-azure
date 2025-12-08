variable "project" {
  description = "Nombre corto del proyecto para nombrar recursos"
  type        = string
  default     = "static-site"
}

variable "location" {
  description = "Región de Azure"
  type        = string
  default     = "westeurope"
}

variable "app_service_sku" {
  description = "SKU del App Service Plan (p.ej. B1, S1, P1v3)"
  type        = string
  default     = "B1"
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
