"""Configuración de la base de datos SQLite de la aplicación."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ventas_app.config import APP_ENCRYPTION_KEY
from ventas_app.crypto import cifrar_texto, es_token_valido

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
    """Agrega las columnas de F13/F14/F16/F17 a una base SQLite anterior.

    ``create_all`` no modifica tablas existentes. Esta migración es idempotente
    y conserva las ventas históricas: las filas previas quedan sin datos de
    pago, sin DDJJ, sin aportes, sin descuento y con el total anterior como
    subtotal base.
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
        if "pago_titular" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN pago_titular VARCHAR(80)"
            )
        if "pago_marca_entidad" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN pago_marca_entidad VARCHAR(80)"
            )
        if "pago_ultimos_4" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN pago_ultimos_4 VARCHAR(4)"
            )
        if "pago_vencimiento" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN pago_vencimiento VARCHAR(5)"
            )
        if "pago_cuil" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN pago_cuil VARCHAR(11)"
            )
        if "ddjj_completada" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN ddjj_completada "
                "BOOLEAN NOT NULL DEFAULT 0"
            )
        if "ddjj_preexistencias" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN ddjj_preexistencias "
                "BOOLEAN NOT NULL DEFAULT 0"
            )
        if "ddjj_internaciones" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN ddjj_internaciones "
                "BOOLEAN NOT NULL DEFAULT 0"
            )
        if "ddjj_embarazo" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN ddjj_embarazo "
                "BOOLEAN NOT NULL DEFAULT 0"
            )
        if "ddjj_medicacion_cronica" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN ddjj_medicacion_cronica "
                "BOOLEAN NOT NULL DEFAULT 0"
            )
        if "ddjj_discapacidad" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN ddjj_discapacidad "
                "BOOLEAN NOT NULL DEFAULT 0"
            )
        if "ddjj_detalle" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN ddjj_detalle TEXT"
            )
        if "regimen_afiliacion" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN regimen_afiliacion "
                "VARCHAR(30) NOT NULL DEFAULT 'PARTICULAR'"
            )
        if "cuil_titular" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN cuil_titular VARCHAR(11)"
            )
        if "aporte_estimado" not in columnas:
            conexion.exec_driver_sql(
                "ALTER TABLE ventas ADD COLUMN aporte_estimado "
                "INTEGER NOT NULL DEFAULT 0"
            )

        if "precio_total" in columnas:
            conexion.exec_driver_sql(
                "UPDATE ventas SET subtotal_base = precio_total "
                "WHERE subtotal_base = 0 AND precio_total > 0"
            )

        _reformar_ventas_para_precio_cero(conexion)


def _reformar_ventas_para_precio_cero(conexion) -> None:
    """Reconstruye la tabla si el CHECK histórico impedía un total cero.

    F17 permite que el aporte cubra toda la base bonificada. Las bases
    anteriores tenían ``CHECK (precio_total > 0)``; SQLite no permite alterar
    un CHECK, así que se reconstruye la tabla conservando las filas.
    """
    fila = conexion.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='ventas'"
    ).fetchone()
    if not fila or "precio_total > 0" not in (fila[0] or ""):
        return

    from sqlalchemy import MetaData

    from ventas_app.models import Plan, Venta

    columnas_modelo = {columna.name for columna in Venta.__table__.columns}
    columnas_actuales = {
        registro[1]
        for registro in conexion.exec_driver_sql("PRAGMA table_info(ventas)")
    }
    if not columnas_modelo.issubset(columnas_actuales):
        return

    from ventas_app.models import Integrante

    columnas_hijos = [columna.name for columna in Integrante.__table__.columns]
    filas_hijos: list[dict[str, object]] = []
    tablas = {
        fila[0]
        for fila in conexion.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "integrantes" in tablas:
        from datetime import date

        filas_hijos = [
            dict(fila)
            for fila in conexion.exec_driver_sql(
                f"SELECT {', '.join(columnas_hijos)} FROM integrantes"
            ).mappings()
        ]
        for fila in filas_hijos:
            if isinstance(fila.get("fecha_nacimiento"), str):
                fila["fecha_nacimiento"] = date.fromisoformat(
                    fila["fecha_nacimiento"]
                )

    conexion.exec_driver_sql("PRAGMA defer_foreign_keys=ON")
    metadata = MetaData()
    Plan.__table__.to_metadata(metadata)
    nueva = Venta.__table__.to_metadata(metadata, name="ventas_f17")
    for indice in list(nueva.indexes):
        nueva.indexes.remove(indice)
    nueva.create(bind=conexion)
    columnas_sql = ", ".join(columna.name for columna in Venta.__table__.columns)
    conexion.exec_driver_sql(
        f"INSERT INTO ventas_f17 ({columnas_sql}) "
        f"SELECT {columnas_sql} FROM ventas"
    )
    conexion.exec_driver_sql("DROP TABLE ventas")
    conexion.exec_driver_sql("ALTER TABLE ventas_f17 RENAME TO ventas")
    for indice in Venta.__table__.indexes:
        indice.create(bind=conexion)

    if "integrantes" in tablas:
        # DROP TABLE dispara ON DELETE CASCADE aunque las FK estén diferidas.
        # Restauramos los hijos desde el respaldo tomado antes del DROP.
        conexion.exec_driver_sql("DELETE FROM integrantes")
        if filas_hijos:
            conexion.execute(Integrante.__table__.insert(), filas_hijos)


def _migrar_campos_sensibles(engine_objetivo: Engine = engine) -> None:
    """Cifra en reposo los detalles de salud históricos en texto plano."""
    if not APP_ENCRYPTION_KEY or engine_objetivo.dialect.name != "sqlite":
        return

    with engine_objetivo.begin() as conexion:
        tablas = {
            fila[0]
            for fila in conexion.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "ventas" not in tablas:
            return
        columnas = {
            fila[1]
            for fila in conexion.exec_driver_sql("PRAGMA table_info(ventas)")
        }
        if "ddjj_detalle" not in columnas:
            return

        filas = conexion.exec_driver_sql(
            "SELECT id, ddjj_detalle FROM ventas "
            "WHERE ddjj_detalle IS NOT NULL AND ddjj_detalle <> ''"
        ).fetchall()
        for venta_id, valor in filas:
            if isinstance(valor, str) and not es_token_valido(valor):
                conexion.exec_driver_sql(
                    "UPDATE ventas SET ddjj_detalle = ? WHERE id = ?",
                    (cifrar_texto(valor), venta_id),
                )


def _endurecer_permisos_db(engine_objetivo: Engine = engine) -> None:
    """Restringe la base SQLite al usuario del servicio."""
    if engine_objetivo.dialect.name != "sqlite":
        return
    ruta = engine_objetivo.url.database
    if not ruta or ruta == ":memory:":
        return
    archivo = Path(ruta)
    if archivo.exists():
        try:
            archivo.chmod(0o600)
        except OSError:
            pass


def init_db() -> None:
    """Crea las tablas registradas en la metadata de ``Base``."""
    # Import local para garantizar que los modelos se registren en Base.metadata
    # sin crear dependencias circulares a nivel de módulo.
    from ventas_app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrar_ventas_sqlite()
    _migrar_campos_sensibles()
    _endurecer_permisos_db()


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI que entrega una sesión y la cierra al finalizar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
