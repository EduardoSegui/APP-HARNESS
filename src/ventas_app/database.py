"""Configuración de la base de datos SQLite de la aplicación."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "ventas.db"

# Permite inyectar una base temporal en tests: DATABASE_URL=sqlite:///./tmp/test.db
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE_PATH}")

_connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(DATABASE_URL, connect_args=_connect_args)


if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        """Activa la integridad referencial en cada conexión SQLite."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


def init_db() -> None:
    """Crea las tablas registradas en la metadata de ``Base``."""
    # Import local para garantizar que los modelos se registren en Base.metadata
    # sin crear dependencias circulares a nivel de módulo.
    from ventas_app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI que entrega una sesión y la cierra al finalizar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
