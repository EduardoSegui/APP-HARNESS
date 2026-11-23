"""Carga de variables de entorno desde el archivo ``.env`` del proyecto."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

# Cargar .env antes de leer las constantes de seguridad.
load_dotenv(dotenv_path=ENV_FILE, override=False)

SESSION_COOKIE_NAME = "vos_session"
SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() != "false"
SESSION_IDLE_MINUTES = int(os.getenv("SESSION_IDLE_MINUTES", "30"))
SESSION_ABSOLUTE_HOURS = int(os.getenv("SESSION_ABSOLUTE_HOURS", "8"))
MFA_ISSUER = os.getenv("MFA_ISSUER", "Ventas Obra Social")
APP_ENCRYPTION_KEY = os.getenv("APP_ENCRYPTION_KEY", "").strip()
LOGIN_RATE_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_WINDOW_SECONDS", "60"))
LOGIN_RATE_MAX_ATTEMPTS = int(os.getenv("LOGIN_RATE_MAX_ATTEMPTS", "5"))
LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))


def cargar_entorno() -> bool:
    """Carga ``.env`` sin sobrescribir variables ya exportadas.

    Se usa una ruta absoluta para que funcione tanto al levantar Uvicorn como
    al ejecutar el auditor o los scripts desde la raíz del repositorio.
    """
    return load_dotenv(dotenv_path=ENV_FILE, override=False)
