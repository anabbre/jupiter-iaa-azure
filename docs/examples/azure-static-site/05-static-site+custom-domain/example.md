# Static Website + Custom Domain (CNAME)

**Crea:**

- Resource Group
- Storage Account (Static Website habilitado)
- Zona DNS (ej. `example.com`)
- CNAME `www.example.com` -> `<account>.z13.web.core.windows.net`

**Validación local (offline):**

```bash
terraform fmt -recursive
terraform init -backend=false
terraform validate
