# 07 – Static Site + Logging

Objetivo: servir el **Static Website** de Azure Storage detrás de **Front Door Standard/Premium** y **enviar logs/métricas** de Storage y Front Door a **Log Analytics** mediante `azurerm_monitor_diagnostic_setting`.

Este ejemplo valida **offline** con:

```bash
terraform fmt -recursive
terraform init -backend=false
terraform validate

