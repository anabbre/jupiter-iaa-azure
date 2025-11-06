output "resource_group" {
  value       = azurerm_resource_group.this.name
  description = "Nombre del RG creado"
}

output "app_service_plan" {
  value       = azurerm_service_plan.this.name
  description = "Nombre del App Service Plan"
}

output "webapp_default_hostname" {
  value       = azurerm_linux_web_app.this.default_hostname
  description = "Hostname por defecto (*.azurewebsites.net)"
}

