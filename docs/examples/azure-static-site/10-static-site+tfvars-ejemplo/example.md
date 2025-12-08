# 10 – Static Site + tfvars (ejemplo)

Objetivo: mostrar cómo parametrizar el despliegue usando `terraform.tfvars`.

Valida offline con:

```bash
terraform fmt -recursive
terraform init -backend=false
terraform validate
