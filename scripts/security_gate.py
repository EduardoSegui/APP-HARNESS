#!/usr/bin/env python3
"""Gate local de seguridad de cadena de suministro.

No instala paquetes con pip. Los scanners opcionales (semgrep/gitleaks) se
ejecutan si están disponibles; CI los instala y ejecuta explícitamente.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "ventas_app" / "static"


def _run(comando: list[str], *, obligatorio: bool = True) -> bool:
    print(f"$ {' '.join(comando)}")
    resultado = subprocess.run(
        comando,
        cwd=ROOT,
        text=True,
        check=False,
    )
    if resultado.returncode != 0:
        if obligatorio:
            print(f"ERROR: falló {' '.join(comando)}", file=sys.stderr)
        return False
    return True


def _verificar_assets() -> bool:
    lock = STATIC / "ASSETS.lock"
    if not lock.is_file():
        print("ERROR: falta ASSETS.lock", file=sys.stderr)
        return False
    for linea in lock.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        ruta, esperado = linea.split()
        archivo = STATIC / ruta
        if not archivo.is_file():
            print(f"ERROR: falta asset {ruta}", file=sys.stderr)
            return False
        real = hashlib.sha256(archivo.read_bytes()).hexdigest()
        if real != esperado:
            print(f"ERROR: hash alterado en {ruta}", file=sys.stderr)
            return False
    print("OK assets self-hosted y hashes")
    return True


def _escanear_secretos_locales() -> bool:
    patrones = (
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    )
    for base in (ROOT / "src", ROOT / "scripts", ROOT / "tests"):
        for archivo in base.rglob("*"):
            if not archivo.is_file() or "__pycache__" in archivo.parts:
                continue
            try:
                texto = archivo.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if any(patron.search(texto) for patron in patrones):
                print(f"ERROR: posible secreto en {archivo}", file=sys.stderr)
                return False
    print("OK escaneo local de secretos")
    return True


def main() -> int:
    obligatorio_ok = True
    obligatorio_ok &= _run(["uv", "lock", "--check"])
    obligatorio_ok &= _run(
        ["uv", "run", "pip-audit", "--progress-spinner", "off"]
    )
    # Solo High/Critical bloquean; los Medium/Low se revisan con contexto.
    obligatorio_ok &= _run(["uv", "run", "bandit", "-q", "-r", "src", "-lll"])
    obligatorio_ok &= _verificar_assets()
    obligatorio_ok &= _escanear_secretos_locales()

    for comando, etiqueta in (
        (
            [
                "semgrep",
                "--config",
                ".semgrep.yml",
                "--error",
                "--quiet",
            ],
            "semgrep",
        ),
        (
            [
                "gitleaks",
                "detect",
                "--source",
                ".",
                "--config",
                ".gitleaks.toml",
                "--no-banner",
                "--redact",
            ],
            "gitleaks",
        ),
    ):
        if shutil_which(comando[0]) is None:
            print(f"SKIP {etiqueta}: no instalado localmente (CI lo ejecuta)")
            continue
        if not _run(comando, obligatorio=False):
            print(f"ADVERTENCIA: {etiqueta} encontró hallazgos", file=sys.stderr)
            obligatorio_ok = False

    if not obligatorio_ok:
        print("❌ Gate de seguridad falló.", file=sys.stderr)
        return 1
    print("✅ Gate de seguridad OK.")
    return 0


def shutil_which(nombre: str) -> str | None:
    from shutil import which

    return which(nombre)


if __name__ == "__main__":
    raise SystemExit(main())
