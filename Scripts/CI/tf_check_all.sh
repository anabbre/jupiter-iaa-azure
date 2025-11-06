#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")"/../.. && pwd)"
EXAMPLES_DIR="$ROOT/docs/examples/azure-static-site"

echo "== Terraform mini-check en $EXAMPLES_DIR =="
echo

# lista fija para mantener el orden
examples=(
  "01-storage-static-website"
  "02-storage+cdn"
  "03-frontdoor-static"
  "04-static-site-app-service"
  "05-static-site+custom-domain"
  "06-static-site+https"
  "07-static-site+logging"
  "08-static-site+diagnostics"
  "09-static-site+alerts"
  "10-static-site+tfvars-ejemplo"
)

fail=0
for ex in "${examples[@]}"; do
  dir="$EXAMPLES_DIR/$ex"
  echo "----> $ex"
  ( cd "$dir"
    terraform fmt -recursive
    terraform init -backend=false -input=false >/dev/null
    terraform validate
  ) || fail=1
  echo
done

if [ "$fail" -ne 0 ]; then
  echo "❌ Algún ejemplo ha fallado."
  exit 1
else
  echo "✅ Todos los ejemplos válidos."
fi
