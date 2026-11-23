#!/usr/bin/env python3
"""Restauración manual de un backup cifrado.

Uso:
    uv run python scripts/restore.py ARCHIVO DESTINO --confirmar

Requiere modo mantenimiento, custodia humana y copia previa. No hay endpoint
web de restauración.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ventas_app.services.backup import ErrorBackup, restaurar_backup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restaurar backup de ventas")
    parser.add_argument("archivo", type=Path)
    parser.add_argument("destino", type=Path)
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Confirma que la app está detenida y el destino es correcto",
    )
    args = parser.parse_args(argv)
    if not args.confirmar:
        print(
            "Restauración cancelada: repetí con --confirmar en modo mantenimiento.",
            file=sys.stderr,
        )
        return 2
    try:
        ruta = restaurar_backup(args.archivo, args.destino)
    except ErrorBackup as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Base restaurada en: {ruta}")
    print("Verificá la app y ejecutá ./init.sh antes de volver a producción.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
