# App Service (Linux) para sitio estático

Crea:

- Resource Group
- App Service Plan (Linux, SKU configurable)
- Linux Web App con TLS 1.2 y FTPS deshabilitado

**Uso típico (local, offline):**

```
terraform fmt -recursive
terraform init -backend=false
terraform validate
```
