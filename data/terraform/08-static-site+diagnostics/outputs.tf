output "static_website_endpoint" {
  description = "URL pública del Static Website"
  value       = azurerm_storage_account.this.primary_web_endpoint
}

output "frontdoor_endpoint_hostname" {
  description = "Hostname público de Front Door"
  value       = azurerm_cdn_frontdoor_endpoint.this.host_name
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.this.id
}
