"""Configuración de la base de datos SQLite de la aplicación."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
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


def _migrar_ventas_sqlite(engine_objetivo: Engine = engine) -> None:
    """Agrega las columnas de F13 a una base SQLite creada con F12 o antes.

    ``create_all`` no modifica tablas existentes. Esta migración es idempotente
    y conserva las ventas históricas: las filas previas quedan sin descuento y
    con el total anterior como subtotal base.
    """
    if engine_objetivo.dialect.name != "sqlite":
        return

    with engine_objetivo.begin() as conexion:
        columnas = {
            fila[1]
            for fila in conexion.exec_driver_sql("PRAGMA table_info(ventas)")
        }
        if not columnas:
            return

        if "medio_pago" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN medio_pago "
                "VARCHAR(30) NOT NULL DEFAULT 'PAGO_FACIL'"
            )
        if "subtotal_base" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN subtotal_base "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "descuento_porcentaje" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN descuento_porcentaje "
                "INTEGER NOT NULL DEFAULT 0"
            )

        if "precio_total" in columnas:
            conexion.exec_driver_sql(
                "UPDATE ventas SET subtotal_base = precio_total "
                "WHERE subtotal_base = 0 AND precio_total > 0"
            )


def init_db() -> None:
    """Crea las tablas registradas en la metadata de ``Base``."""
    # Import local para garantizar que los modelos se registren en Base.metadata
    # sin crear dependencias circulares a nivel de módulo.
    from ventas_app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrar_ventas_sqlite()


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI que entrega una sesión y la cierra al finalizar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
