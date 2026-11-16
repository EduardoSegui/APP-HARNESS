#!/usr/bin/env bash
#
# Verificación integral del harness.
# Uso: ./init.sh
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "==> [1/3] Verificando disponibilidad de uv"
if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv no está instalado o no está en PATH." >&2
    echo "Instalación: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi
uv --version

echo "==> [2/3] Verificando archivos obligatorios del harness"
required_files=(
    "AGENTS.md"
    "features.json"
    "CHECKPOINT.md"
)
required_dirs=(
    "src/ventas_app"
)

for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "ERROR: falta el archivo obligatorio '$file'." >&2
        exit 1
    fi
    echo "    OK archivo: $file"
done

for dir in "${required_dirs[@]}"; do
    if [[ ! -d "$dir" ]]; then
        echo "ERROR: falta el directorio obligatorio '$dir'." >&2
        exit 1
    fi
    echo "    OK directorio: $dir"
done

echo "==> [3/3] Ejecutando la suite de tests"
uv run pytest

echo ""
echo "✅ Harness verificado correctamente."
