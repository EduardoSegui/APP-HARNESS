"""Punto de entrada de la aplicación FastAPI."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ventas_app.config import ALLOWED_HOSTS, ENABLE_DOCS
from ventas_app.database import SessionLocal, init_db
from ventas_app.middleware import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from ventas_app.routers.api import router as api_router
from ventas_app.routers.auth import router as auth_router
from ventas_app.routers.privacidad import router as privacidad_router
from ventas_app.routers.web import STATIC_DIR, router as web_router
from ventas_app.seed import seed_planes
from ventas_app.services.privacidad import asegurar_politicas_default


class _UvicornAccessFilter(logging.Filter):
    """Quita query strings de los access logs de Uvicorn."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            argumentos = list(record.args)
            argumentos[2] = str(argumentos[2]).split("?", 1)[0]
            record.args = tuple(argumentos)
        return True


_access_logger = logging.getLogger("uvicorn.access")
if not any(
    isinstance(filtro, _UvicornAccessFilter)
    for filtro in _access_logger.filters
):
    _access_logger.addFilter(_UvicornAccessFilter())


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Inicializa la base de datos y siembra los planes al arrancar."""
    init_db()
    with SessionLocal() as db:
        seed_planes(db)
        asegurar_politicas_default(db)
    yield


app = FastAPI(
    title="Ventas Obra Social",
    description="Carga y validación agéntica de ventas de obra social.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(ALLOWED_HOSTS))
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_router)
app.include_router(privacidad_router)
app.include_router(api_router)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(RequestValidationError)
async def validacion_segura(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """No devuelve valores de entrada, CVV, PAN ni salud en el 422."""
    detalle = [
        {
            clave: valor
            for clave, valor in error.items()
            if clave in {"loc", "msg", "type"}
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": detalle},
    )


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    """Devuelve el estado de salud de la aplicación."""
    return {"status": "ok"}
