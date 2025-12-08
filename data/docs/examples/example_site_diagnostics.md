# 08 – Static Site + Diagnostics (Azure Monitor)

Objetivo: servir el Static Website de Azure Storage detrás de **Front Door Standard/Premium** y habilitar **Diagnostic Settings** enviando logs/métricas a **Log Analytics**.

> Este ejemplo valida **offline** con:
>
> ```bash
> terraform fmt -recursive
> terraform init -backend=false
> terraform validate
> ```
