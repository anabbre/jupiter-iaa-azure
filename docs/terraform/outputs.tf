output "website_url" {
  description = "URL pública del sitio estático en Azure Storage"
  value       = azurerm_storage_account.sa.primary_web_endpoint
}
