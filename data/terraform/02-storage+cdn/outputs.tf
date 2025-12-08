output "static_website_primary_endpoint" {
  description = "URL pública del Static Website (nativa de Storage)"
  value       = azurerm_storage_account.this.primary_web_endpoint
}

output "cdn_endpoint_hostname" {
  description = "Hostname del CDN que sirve el sitio estático"
  value       = "${azurerm_cdn_endpoint.this.name}.azureedge.net"
}

output "cdn_public_url" {
  description = "URL https pública a través del CDN"
  value       = "https://${azurerm_cdn_endpoint.this.name}.azureedge.net"
}

