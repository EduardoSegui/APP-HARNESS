"""Configuración común de la suite de tests."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

# La URL debe configurarse antes de importar ventas_app.database.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="ventas-app-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR / 'ventas-test.db'}"

from ventas_app import models  # noqa: E402, F401
from ventas_app.database import Base, SessionLocal, engine  # noqa: E402
from ventas_app.models import Integrante, Plan, Venta  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def base_de_datos_temporal() -> Iterator[None]:
    """Crea el esquema en una base SQLite temporal aislada de desarrollo."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def limpiar_tablas(base_de_datos_temporal: None) -> Iterator[None]:
    """Deja las tablas vacías antes de cada test."""
    with SessionLocal() as db:
        db.execute(delete(Integrante))
        db.execute(delete(Venta))
        db.execute(delete(Plan))
        db.commit()
    yield


@pytest.fixture
def db() -> Iterator[Session]:
    """Sesión de base de datos para un test."""
    with SessionLocal() as session:
        yield session
