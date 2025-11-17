# 06 – Static Site + HTTPS (Front Door)

Objetivo: servir el Static Website de Azure Storage detrás de **Front Door Standard/Premium**, **forzando HTTPS** y añadiendo **HSTS**.

- `azurerm_cdn_frontdoor_route.https_redirect_enabled = true` aplica redirección automática a HTTPS.
- `azurerm_cdn_frontdoor_rule_set` + `azurerm_cdn_frontdoor_rule` añade la cabecera `Strict-Transport-Security`.

> Este ejemplo valida **offline** con:
>
> ```bash
> terraform fmt -recursive
> terraform init -backend=false
> terraform validate
> ```
