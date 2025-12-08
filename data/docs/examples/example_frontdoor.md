# 03 - Static Website con Azure Front Door

**Qué hace**  
Crea:

- Un **Resource Group**.
- Una **Storage Account** con **Static Website** (index y 404).
- Un perfil y endpoint de **Azure Front Door (Standard)**.
- Un **origin group** y **origin** apuntando al host público del Static Website.
- Una **route** que enruta `/*` hacia el origen y fuerza **HTTPS**.

**Por qué**  
Es el patrón típico “sitio estático + CDN/Front Door” para mejorar rendimiento y seguridad.

**Archivos**

- `main.tf`: define todos los recursos.
- `variables.tf`: parámetros editables (RG, cuenta, SKU, etc.).
- `outputs.tf`: muestra URLs útiles (endpoint Storage y hostname AFD).
- `terraform.tfvars.example`: valores de ejemplo para reproducibilidad local.

**Notas**

- No hay `backend` de Terraform; se valida en **modo offline** con `init -backend=false`.
- El nombre de `storage_account_name` debe ser **único y minúsculas**.
