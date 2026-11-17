"""Carga de variables de entorno desde el archivo ``.env`` del proyecto."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def cargar_entorno() -> bool:
    """Carga ``.env`` sin sobrescribir variables ya exportadas.

    Se usa una ruta absoluta para que funcione tanto al levantar Uvicorn como
    al ejecutar el auditor o los scripts desde la raíz del repositorio.
    """
    return load_dotenv(dotenv_path=ENV_FILE, override=False)
