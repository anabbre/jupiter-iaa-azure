terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# Sufijo aleatorio para garantizar nombre global único del Web App
resource "random_id" "suffix" {
  byte_length = 3
}

# Resource Group
resource "azurerm_resource_group" "this" {
  name     = "${var.project}-rg"
  location = var.location
  tags     = var.tags
}

# App Service Plan (Linux)
resource "azurerm_service_plan" "this" {
  name                = "${var.project}-asp"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name

  os_type  = "Linux"
  sku_name = var.app_service_sku # p.ej. "B1", "S1", etc.

  tags = var.tags
}

# Web App (Linux) para servir sitio estático (deploy de contenidos fuera de este ejemplo)
resource "azurerm_linux_web_app" "this" {
  name                = "${var.project}-app-${random_id.suffix.hex}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  service_plan_id     = azurerm_service_plan.this.id

  https_only = true

  site_config {
    minimum_tls_version = "1.2"
    ftps_state          = "Disabled"
  }

  tags = var.tags
}
