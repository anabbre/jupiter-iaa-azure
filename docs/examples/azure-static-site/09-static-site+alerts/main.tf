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
  sa_name = lower(var.storage_account_name)
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
resource "azurerm_cdn_frontdoor_profile" "this" {
  name                = "${var.project}-afd-prof"
  resource_group_name = azurerm_resource_group.this.name
  sku_name            = var.front_door_sku_name # p.ej. "Standard_AzureFrontDoor"
  tags                = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "this" {
  name                     = "${var.project}-afd-endp"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  tags                     = var.tags
}

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

  # el Static Website expone 'primary_web_host'
  host_name = azurerm_storage_account.this.primary_web_host

  http_port                      = 80
  https_port                     = 443
  enabled                        = true
  priority                       = 1
  weight                         = 1000
  certificate_name_check_enabled = true

  depends_on = [azurerm_storage_account_static_website.this]
}

# Ruta: enlaza endpoint con el origen
resource "azurerm_cdn_frontdoor_route" "this" {
  name                          = "${var.project}-route"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.this.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.this.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.static_site_origin.id]

  supported_protocols    = ["Http", "Https"]
  https_redirect_enabled = true
  link_to_default_domain = true
  patterns_to_match      = ["/*"]

  depends_on = [azurerm_storage_account_static_website.this]
}

# Log Analytics (para futuras reglas basadas en logs si quisieras)
resource "azurerm_log_analytics_workspace" "this" {
  name                = var.log_analytics_workspace_name
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_days
  tags                = var.tags
}

# Action Group (destinatarios de alertas)
resource "azurerm_monitor_action_group" "this" {
  name                = "${var.project}-ag"
  resource_group_name = azurerm_resource_group.this.name
  short_name          = "alerts"

  email_receiver {
    name                    = "email"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }

  tags = var.tags
}

# MÉTRIC ALERTS

# 1) Storage: demasiadas transacciones (ejemplo)
resource "azurerm_monitor_metric_alert" "storage_tx" {
  name                = "${var.project}-alert-storage-tx"
  resource_group_name = azurerm_resource_group.this.name
  scopes              = [azurerm_storage_account.this.id]
  description         = "Transacciones de Storage por encima del umbral (ejemplo)."
  severity            = 3
  frequency           = "PT5M"
  window_size         = "PT5M"
  auto_mitigate       = true
  enabled             = true

  criteria {
    metric_namespace = "Microsoft.Storage/storageAccounts"
    metric_name      = "Transactions"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = var.storage_tx_threshold
  }

  action {
    action_group_id = azurerm_monitor_action_group.this.id
  }

  tags = var.tags
}

# 2) Front Door: muchas peticiones totales (ejemplo)
resource "azurerm_monitor_metric_alert" "afd_total_requests" {
  name                = "${var.project}-alert-afd-req"
  resource_group_name = azurerm_resource_group.this.name
  scopes              = [azurerm_cdn_frontdoor_profile.this.id]
  description         = "TotalRequests de Front Door por encima del umbral (ejemplo)."
  severity            = 3
  frequency           = "PT5M"
  window_size         = "PT5M"
  auto_mitigate       = true
  enabled             = true

  criteria {
    metric_namespace = "Microsoft.Cdn/profiles"
    metric_name      = "TotalRequests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = var.afd_total_requests_threshold
  }

  action {
    action_group_id = azurerm_monitor_action_group.this.id
  }

  tags = var.tags
}
