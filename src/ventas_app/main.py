"""Punto de entrada de la aplicación FastAPI."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ventas_app.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Inicializa la base de datos al arrancar la aplicación."""
    init_db()
    yield


app = FastAPI(
    title="Ventas Obra Social",
    description="Carga y validación agéntica de ventas de obra social.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    """Devuelve el estado de salud de la aplicación."""
    return {"status": "ok"}
