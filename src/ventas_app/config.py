"""Carga de variables de entorno desde el archivo ``.env`` del proyecto."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
_SKIP_DOTENV = os.getenv("VENTAS_SKIP_DOTENV") == "1"

# Cargar .env antes de leer las constantes de seguridad. El subproceso MCP
# usa VENTAS_SKIP_DOTENV=1 para no heredar claves LLM desde el archivo.
if not _SKIP_DOTENV:
    load_dotenv(dotenv_path=ENV_FILE, override=False)
    if ENV_FILE.exists():
        try:
            ENV_FILE.chmod(0o600)
        except OSError:
            pass

SESSION_COOKIE_NAME = "vos_session"
SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() != "false"
SESSION_IDLE_MINUTES = int(os.getenv("SESSION_IDLE_MINUTES", "30"))
SESSION_ABSOLUTE_HOURS = int(os.getenv("SESSION_ABSOLUTE_HOURS", "8"))
MFA_ISSUER = os.getenv("MFA_ISSUER", "Ventas Obra Social")
APP_ENCRYPTION_KEY = os.getenv("APP_ENCRYPTION_KEY", "").strip()
BACKUP_ENCRYPTION_KEY = (
    os.getenv("BACKUP_ENCRYPTION_KEY", "").strip() or APP_ENCRYPTION_KEY
)
BACKUP_DIR = Path(
    os.getenv("BACKUP_DIR", str(PROJECT_ROOT / "backups"))
).expanduser()
BACKUP_OFFLINE_DIR = Path(
    os.getenv("BACKUP_OFFLINE_DIR", "").strip()
    or str(BACKUP_DIR / "offline")
).expanduser()
BACKUP_RETENTION_DAILY = int(os.getenv("BACKUP_RETENTION_DAILY", "7"))
BACKUP_RETENTION_WEEKLY = int(os.getenv("BACKUP_RETENTION_WEEKLY", "4"))
BACKUP_RETENTION_OFFLINE = int(os.getenv("BACKUP_RETENTION_OFFLINE", "1"))
LOGIN_RATE_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_WINDOW_SECONDS", "60"))
LOGIN_RATE_MAX_ATTEMPTS = int(os.getenv("LOGIN_RATE_MAX_ATTEMPTS", "5"))
LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", str(256 * 1024)))
MAX_INTEGRANTES = int(os.getenv("MAX_INTEGRANTES", "20"))
MAX_EXPORT_ROWS = int(os.getenv("MAX_EXPORT_ROWS", "5000"))
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
HSTS_ENABLED = os.getenv("HSTS_ENABLED", "false").lower() == "true"
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "false").lower() == "true"
ALLOWED_HOSTS = tuple(
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1,testserver",
    ).split(",")
    if host.strip()
)


def cargar_entorno() -> bool:
    """Carga ``.env`` sin sobrescribir variables ya exportadas.

    Se usa una ruta absoluta para que funcione tanto al levantar Uvicorn como
    al ejecutar el auditor o los scripts desde la raíz del repositorio. El
    subproceso MCP puede desactivar la carga con ``VENTAS_SKIP_DOTENV=1``.
    """
    if _SKIP_DOTENV:
        return False
    cargado = load_dotenv(dotenv_path=ENV_FILE, override=False)
    if ENV_FILE.exists():
        try:
            ENV_FILE.chmod(0o600)
        except OSError:
            pass
    return cargado
