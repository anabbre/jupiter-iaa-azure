Este directorio contiene **10 ejemplos autocontenidos** de infraestructura en Azure para servir *static websites* y variantes habituales (CDN/Front Door, dominio custom, HTTPS/HSTS, logging, diagnósticos, alertas y uso de `*.tfvars`). Todos los ejemplos están pensados para **validarse en local y en CI sin tocar Azure** (backend deshabilitado, sin `terraform apply`).

> **Objetivo del repo**: integrar estos ejemplos en la base vectorial y poder pedir al asistente **código Terraform** para resolver escenarios comunes de *static site* en Azure, con referencia real y actualizada.

---

## Índice de ejemplos

1. **01-storage-static-website** — Static Website sobre `azurerm_storage_account_static_website`.
2. **02-storage+cdn** — Storage + CDN clásico (`azurerm_cdn_profile` + `azurerm_cdn_endpoint`).
3. **03-frontdoor-static** — Front Door (Standard/Premium) como reverse‑proxy delante del static website.
4. **04-static-site-app-service** — Variante con *Static Web Apps* (App Service SKU).
5. **05-static-site+custom-domain** — Dominio personalizado y validaciones DNS (TXT).
6. **06-static-site+https** — Front Door con **redirección a HTTPS** y cabecera **HSTS**.
7. **07-static-site+logging** — Envío de logs/métricas a **Log Analytics** (LAW) + *diagnostic settings* (solo validación).
8. **08-static-site+diagnostics** — Ejemplo centrado en *diagnostic settings* preparado para preguntas del asistente.
9. **09-static-site+alerts** — Alertas básicas (p. ej. estado/latencia de Front Door) con *Action Group*.
10. **10-static-site+tfvars-ejemplo** — Uso de `terraform.tfvars` como patrón de parametrización.

Cada carpeta incluye: `main.tf`, `variables.tf`, `outputs.tf` y `terraform.tfvars` (ya preparado para validar sin tocar nada).

---

## Requisitos mínimos

- **Terraform ≥ 1.5.0**
- Provider **azurerm ~> 3.100** (el *lockfile* fija la 3.117.x usada en el proyecto).
- Linux/macOS/WSL con `bash` para la validación local.

> **Nota sobre *warnings***: algunos ejemplos muestran `azurerm_monitor_diagnostic_setting` con `retention_policy` o `log {}` **deprecado**. No impide `terraform validate`.

---

## Cómo probar en local (modo offline)

### Opción A — Carpeta a carpeta

Dentro de cada ejemplo:

```bash
terraform fmt -recursive
terraform init -backend=false
terraform validate
```

> Ejemplo:  
> `cd data\terraform/06-static-site+https && terraform init -backend=false && terraform validate`

### Opción B — Comando único (todos los ejemplos)

Ya hay un *mini‑check* local para pasar **todos** los ejemplos en orden:

```bash
make tf-check
```

Esto ejecuta `Scripts/CI/tf_check_all.sh`, que recorre `data\terraform/*`, hace `fmt`, `init -backend=false -input=false` y `validate`.  
Si algún ejemplo falla, el script devuelve **exit 1**.

---

## Validación en CI (GitHub Actions)

El workflow **`.github/workflows/terraform-validate.yml`** ya está configurado para:

- Dispararse en *push/PR* cuando cambien rutas bajo `docs/examples/**` (o el propio YAML).
- Instalar **Terraform 1.9.x**, ejecutar `fmt`, `init -backend=false` y `validate` en **cada carpeta detectada**.
- Subir artefactos con logs/estados si hubiera fallos, para facilitar el diagnóstico.

No es necesario añadir más workflows para la validación de estos ejemplos.

---

## Variables y `terraform.tfvars` (patrón)

Aunque cada ejemplo incluye su `terraform.tfvars`, este es el **bloque genérico** que puedes reutilizar para pruebas locales o clonado de ejemplos:

```hcl
project              = "static-site"
location             = "westeurope"
resource_group_name  = "rg-static-site-demo"
storage_account_name = "ststaticsitedemo123" # único global y en minúsculas

# Front Door (cuando aplique)
front_door_sku_name = "Standard_AzureFrontDoor"

# Log Analytics (cuando aplique)
log_analytics_workspace_name = "law-static-demo"
log_analytics_retention_days = 30

tags = {
  env     = "dev"
  project = "static-site"
  owner   = "demo"
}
```

---

## ¿Qué pedirle al asistente (RAG)?

El objetivo es que el asistente **genere código Terraform**, haga preguntas de afinado (nombres, regiones, SKU, etc.) y entregue un *snippet* listo para pegar.

Ejemplos de *prompts* útiles:

- **“Fuerza HTTPS y añade HSTS con Front Door para un static site”** → Regla con `https_redirect_enabled = true` y cabecera `Strict-Transport-Security` como en `06-static-site+https`.
- **“Envía logs de Front Door y del Storage a Log Analytics durante 30 días”** → `azurerm_monitor_diagnostic_setting` + LAW como en `07`/`08`.
- **“Configura un dominio personalizado para mi static website (validación TXT previa)”** → Basado en `05-static-site+custom-domain`.
- **“Crea alertas si el endpoint de Front Door falla”** → Ejemplo `09-static-site+alerts` con *Action Group* y regla.
- **“Dame la plantilla base con variables y `terraform.tfvars` para clonar un ejemplo”** → Se apoya en `10-static-site+tfvars-ejemplo`.

---

## Convenciones del directorio

- **Estilo**: HCL formateado (`terraform fmt`) y validado (`terraform validate`).
- **`depends_on`** sólo cuando aclara el orden lógico (p. ej., orígenes detrás del Static Website).
- **Nombrado**: recursos prefijados con el valor de `project` para coherencia.

---

## Troubleshooting rápido

- **`host_name` de origen en CDN/Front Door**: usa `azurerm_storage_account.this.primary_web_host` (sin `https://`).  
- **Errores por atributos inexistentes**: revisa que las *outputs* apunten a `.host_name` y no a `this.host_name` si el recurso no lo expone como tal.
- **Warnings de `retention_policy`**: son esperados en `azurerm_monitor_diagnostic_setting`. Para retención real usar `azurerm_storage_management_policy`.
