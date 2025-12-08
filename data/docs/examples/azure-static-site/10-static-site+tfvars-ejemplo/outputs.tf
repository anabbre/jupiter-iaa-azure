output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "static_website_primary_endpoint" {
  description = "URL pública del Static Website"
  value       = azurerm_storage_account.this.primary_web_endpoint
}

output "static_website_primary_host" {
  description = "Hostname del Static Website (sin esquema)"
  value       = azurerm_storage_account.this.primary_web_host
}
