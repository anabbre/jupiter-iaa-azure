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

# Nombre normalizado para la cuenta de Storage
locals {
  sa_name = lower(var.storage_account_name)
}

# Resource Group
resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# Storage Account (requerido para Static Website)
resource "azurerm_storage_account" "this" {
  name                     = local.sa_name
  resource_group_name      = azurerm_resource_group.this.name
  location                 = azurerm_resource_group.this.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  account_kind             = "StorageV2" # requerido para static website
  tags                     = var.tags
}

# Static Website
resource "azurerm_storage_account_static_website" "this" {
  storage_account_id = azurerm_storage_account.this.id
  index_document     = var.index_document
  error_404_document = var.error_document
}

# CDN clásico (Profile + Endpoint) 
resource "azurerm_cdn_profile" "this" {
  name                = "${var.project}-cdn"
  location            = "Global"
  resource_group_name = azurerm_resource_group.this.name
  sku                 = var.cdn_sku # p. ej. Standard_Microsoft
  tags                = var.tags
}

resource "azurerm_cdn_endpoint" "this" {
  name                = "${var.project}-cdn-endpoint"
  profile_name        = azurerm_cdn_profile.this.name
  location            = "Global"
  resource_group_name = azurerm_resource_group.this.name

  is_http_allowed  = false
  is_https_allowed = true

  # Origen: el host del Static Website (sin https://)
  origin {
    name      = "staticweb"
    host_name = azurerm_storage_account.this.primary_web_host
  }

  # Opcional: comportamiento de caché
  querystring_caching_behaviour = "IgnoreQueryString"

  depends_on = [azurerm_storage_account_static_website.this]
  tags       = var.tags
}
