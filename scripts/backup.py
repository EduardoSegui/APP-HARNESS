#!/usr/bin/env python3
"""CLI de backups cifrados y retención.

Uso:
    uv run python scripts/backup.py crear [--tipo diario|semanal]
    uv run python scripts/backup.py verificar ARCHIVO
    uv run python scripts/backup.py retencion [--tipo diario|semanal|offline]
    uv run python scripts/backup.py offline
    uv run python scripts/backup.py listar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ventas_app.config import BACKUP_DIR, BACKUP_OFFLINE_DIR
from ventas_app.services.backup import (
    ErrorBackup,
    aplicar_retencion,
    copiar_offline,
    crear_backup,
    listar_backups,
    verificar_backup,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backups cifrados de ventas")
    parser.add_argument(
        "comando",
        choices=["crear", "verificar", "retencion", "offline", "listar"],
    )
    parser.add_argument(
        "archivo",
        nargs="?",
        help="Archivo a verificar (solo comando verificar)",
    )
    parser.add_argument(
        "--tipo",
        choices=["diario", "semanal", "offline"],
        default="diario",
    )
    parser.add_argument(
        "--directorio",
        default=None,
        help="Directorio de backups (default: BACKUP_DIR)",
    )
    parser.add_argument(
        "--offline-directorio",
        default=None,
        help="Directorio offline (default: BACKUP_OFFLINE_DIR)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    directorio = Path(args.directorio) if args.directorio else BACKUP_DIR
    offline_dir = (
        Path(args.offline_directorio)
        if args.offline_directorio
        else BACKUP_OFFLINE_DIR
    )

    try:
        if args.comando == "crear":
            info = crear_backup(tipo=args.tipo, directorio=directorio)
            aplicar_retencion(directorio, tipo=args.tipo)
            print(f"Backup creado: {info.ruta}")
            print(f"Checksum: {info.checksum}")
            return 0
        if args.comando == "verificar":
            if not args.archivo:
                print("Falta el archivo a verificar.", file=sys.stderr)
                return 2
            ok = verificar_backup(args.archivo)
            print("Backup válido." if ok else "Backup INVÁLIDO.")
            return 0 if ok else 1
        if args.comando == "retencion":
            eliminados = aplicar_retencion(directorio, tipo=args.tipo)
            print(f"Backups eliminados: {len(eliminados)}")
            return 0
        if args.comando == "offline":
            info = copiar_offline(
                directorio_semanal=directorio,
                directorio_offline=offline_dir,
            )
            print(f"Copia offline: {info.ruta}")
            return 0
        for ruta in listar_backups(directorio):
            print(ruta)
        return 0
    except ErrorBackup as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
