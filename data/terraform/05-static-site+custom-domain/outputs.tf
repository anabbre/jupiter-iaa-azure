output "static_website_endpoint" {
  description = "URL pública del Static Website"
  value       = azurerm_storage_account.this.primary_web_endpoint
}

output "static_website_host" {
  description = "Host público del Static Website"
  value       = azurerm_storage_account.this.primary_web_host
}

output "custom_domain_fqdn" {
  description = "FQDN del dominio personalizado (registro CNAME)"
  value       = "${var.custom_domain_record_name}.${var.custom_domain_zone_name}"
}

output "cname_target" {
  description = "Objetivo del CNAME (debe apuntar al host público del sitio estático)"
  value       = azurerm_storage_account.this.primary_web_host
}
