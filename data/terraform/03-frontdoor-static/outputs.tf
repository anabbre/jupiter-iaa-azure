output "resource_group" {
  value       = azurerm_resource_group.this.name
  description = "Nombre del RG"
}

output "static_website_url" {
  value       = azurerm_storage_account.this.primary_web_endpoint
  description = "URL pública del Static Website"
}

output "frontdoor_endpoint_hostname" {
  value       = azurerm_cdn_frontdoor_endpoint.this.host_name
  description = "Host del endpoint de Azure Front Door"
}

