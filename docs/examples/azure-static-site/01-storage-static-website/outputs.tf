output "static_website_endpoint" {
  description = "URL pública del Static Website"
  value       = azurerm_storage_account.this.primary_web_endpoint
}

output "resource_group" {
  value = azurerm_resource_group.this.name
}
