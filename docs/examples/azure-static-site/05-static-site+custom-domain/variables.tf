variable "project" {
  description = "Nombre corto del proyecto"
  type        = string
  default     = "static-site"
}

variable "location" {
  description = "Región de Azure"
  type        = string
  default     = "westeurope"
}

variable "storage_account_name" {
  description = "Nombre único para la cuenta de Storage (minúsculas, 3–24, letras/números)"
  type        = string
  default     = "ststaticsitedemo123"
}

variable "index_document" {
  description = "Documento de inicio del sitio estático"
  type        = string
  default     = "index.html"
}

variable "error_document" {
  description = "Documento de error del sitio estático"
  type        = string
  default     = "404.html"
}

variable "custom_domain_zone_name" {
  description = "Zona DNS del dominio (ej. example.com)"
  type        = string
  default     = "example.com"
}

variable "custom_domain_record_name" {
  description = "Registro CNAME (ej. www)"
  type        = string
  default     = "www"
}

variable "dns_ttl" {
  description = "TTL del registro CNAME"
  type        = number
  default     = 300
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
