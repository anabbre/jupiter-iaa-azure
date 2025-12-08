# 02 — Static Website en Storage con Azure CDN

Crea un sitio estático en **Azure Storage** (Static Website) y lo publica a través de un **Azure CDN** clásico.  
Útil para mejorar latencia, caché y TLS gestionado en el edge.

**Recursos**: `azurerm_resource_group`, `azurerm_storage_account`, `azurerm_storage_account_static_website`, `azurerm_cdn_profile`, `azurerm_cdn_endpoint`.

> Validación local/offline: `terraform init -backend=false && terraform validate`
