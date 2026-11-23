#!/usr/bin/env bash
#
# Verificación integral del harness.
# Uso: ./init.sh
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "==> [1/5] Verificando disponibilidad de uv"
if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv no está instalado o no está en PATH." >&2
    echo "Instalación: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi
uv --version

echo "==> [2/5] Verificando archivos obligatorios del harness"
required_files=(
    "CONSTITUTION.md"
    "AGENTS.md"
    "features.json"
    "CHECKPOINT.md"
    "STATE.md"
    ".agent/rules.md"
    ".agent/subagents/builder.md"
    ".agent/subagents/verifier.md"
)
required_dirs=(
    "src/ventas_app"
    "docs/journal"
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

echo "==> [3/5] Verificando presupuesto de contexto"
uv run python scripts/contexto.py --check

echo "==> [4/5] Ejecutando la suite de tests"
uv run pytest

echo "==> [5/5] Ejecutando gate de seguridad"
uv run python scripts/security_gate.py

echo ""
echo "✅ Harness verificado correctamente."
