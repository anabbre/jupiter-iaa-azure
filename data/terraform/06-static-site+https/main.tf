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
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# Storage Account + Static Website (origen)
locals {
  sa_name = lower(var.storage_account_name) # debe ser único global
}

resource "azurerm_storage_account" "this" {
  name                     = local.sa_name
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

# Azure Front Door (Standard/Premium)

# Perfil 
resource "azurerm_cdn_frontdoor_profile" "this" {
  name                = "${var.project}-afd-prof"
  resource_group_name = azurerm_resource_group.this.name
  sku_name            = var.front_door_sku_name # p.ej. "Standard_AzureFrontDoor"
  tags                = var.tags
}

# Endpoint público
resource "azurerm_cdn_frontdoor_endpoint" "this" {
  name                     = "${var.project}-afd-endp"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
}

# Grupo de orígenes (load balancing + health probe)
resource "azurerm_cdn_frontdoor_origin_group" "this" {
  name                     = "${var.project}-afd-origrp"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id

  load_balancing {
    sample_size                 = 4
    successful_samples_required = 3
  }

  health_probe {
    path                = "/"
    request_type        = "HEAD"
    protocol            = "Https"
    interval_in_seconds = 100
  }
}

# Origen: host público del Static Website del Storage (sin https://)
resource "azurerm_cdn_frontdoor_origin" "static_site_origin" {
  name                          = "${var.project}-origin"
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.this.id

  # El Static Website expone 'primary_web_host' (solo hostname)
  host_name = azurerm_storage_account.this.primary_web_host

  http_port                      = 80
  https_port                     = 443
  enabled                        = true
  priority                       = 1
  weight                         = 1000
  certificate_name_check_enabled = true

  depends_on = [azurerm_storage_account_static_website.this]
}

# Ruta: enlaza endpoint con el origen y fuerza HTTPS
resource "azurerm_cdn_frontdoor_route" "this" {
  name                          = "${var.project}-route"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.this.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.this.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.static_site_origin.id]

  supported_protocols    = ["Http", "Https"] # acepta ambos...
  https_redirect_enabled = true              # ...pero redirige a HTTPS

  link_to_default_domain = true
  patterns_to_match      = ["/*"]

  depends_on = [azurerm_storage_account_static_website.this]
}
