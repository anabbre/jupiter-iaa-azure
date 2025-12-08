# 09 – Static Site + Alerts

Objetivo: añadir **alertas** sobre métricas de **Storage** y **Front Door**, notificando a un **Action Group** por email.

Este ejemplo valida **offline** con:

```bash
terraform fmt -recursive
terraform init -backend=false
terraform validate
