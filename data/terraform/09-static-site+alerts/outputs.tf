output "static_website_endpoint" {
  description = "URL pública del Static Website"
  value       = azurerm_storage_account.this.primary_web_endpoint
}

output "frontdoor_endpoint_hostname" {
  description = "Hostname público de Front Door"
  value       = azurerm_cdn_frontdoor_endpoint.this.host_name
}

output "action_group_id" {
  value = azurerm_monitor_action_group.this.id
}

output "metric_alert_storage_id" {
  value = azurerm_monitor_metric_alert.storage_tx.id
}

output "metric_alert_afd_id" {
  value = azurerm_monitor_metric_alert.afd_total_requests.id
}
