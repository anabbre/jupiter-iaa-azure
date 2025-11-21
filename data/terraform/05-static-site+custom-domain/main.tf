terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

provider "azurerm" {
  features {}
}

# Resource Group
resource "azurerm_resource_group" "this" {
  name     = "${var.project}-rg"
  location = var.location
  tags     = var.tags
}

# Storage Account con Static Website habilitado
resource "azurerm_storage_account" "this" {
  name                     = lower(var.storage_account_name) # nombre global único
  resource_group_name      = azurerm_resource_group.this.name
  location                 = azurerm_resource_group.this.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  account_kind             = "StorageV2"
  tags                     = var.tags
}

resource "azurerm_storage_account_static_website" "this" {
  storage_account_id = azurerm_storage_account.this.id
  index_document     = var.index_document
  error_404_document = var.error_document
}

# === Custom Domain (solo DNS) ===
# Zona DNS (p. ej. example.com)
resource "azurerm_dns_zone" "this" {
  name                = var.custom_domain_zone_name # ejemplo: "example.com"
  resource_group_name = azurerm_resource_group.this.name
  tags                = var.tags
}

# CNAME (p. ej. www.example.com -> <account>.z13.web.core.windows.net)
resource "azurerm_dns_cname_record" "static_site_cname" {
  name                = var.custom_domain_record_name # ejemplo: "www"
  zone_name           = azurerm_dns_zone.this.name
  resource_group_name = azurerm_resource_group.this.name
  ttl                 = var.dns_ttl

  record = azurerm_storage_account.this.primary_web_host
  # primary_web_host suele tener forma: <account>.z13.web.core.windows.net
}

# Nota: la federación/validación de dominio del propio servicio la haremos después
# (Front Door o enlazado en Static Web Apps), pero para el MVP del chatbot
# nos basta con modelar la intención: un CNAME hacia el host público del sitio estático.
