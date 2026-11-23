"""Middlewares de seguridad y límites para la aplicación."""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ventas_app.config import (
    HSTS_ENABLED,
    MAX_BODY_BYTES,
    RATE_LIMIT_ENABLED,
)

logger = logging.getLogger("ventas_app.access")

_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.tailwindcss.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)
_PERMISSIONS = "camera=(), microphone=(), geolocation=(), payment=()"


class SecurityHeadersMiddleware:
    """Agrega headers defensivos y evita caché de datos sensibles."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_con_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.extend(
                    [
                        (b"content-security-policy", _CSP.encode()),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"permissions-policy", _PERMISSIONS.encode()),
                        (b"x-robots-tag", b"noindex, nofollow"),
                    ]
                )
                if HSTS_ENABLED:
                    headers.append(
                        (
                            b"strict-transport-security",
                            b"max-age=31536000; includeSubDomains",
                        )
                    )
                if not scope.get("path", "").startswith("/static/"):
                    headers.append((b"cache-control", b"no-store"))
            await send(message)

        await self.app(scope, receive, send_con_headers)


class BodySizeLimitMiddleware:
    """Rechaza requests con Content-Length superior al límite."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for clave, valor in scope.get("headers", []):
                if clave.lower() == b"content-length":
                    try:
                        if int(valor) > MAX_BODY_BYTES:
                            response = JSONResponse(
                                {"detail": "Request demasiado grande."},
                                status_code=413,
                            )
                            await response(scope, receive, send)
                            return
                    except ValueError:
                        pass
        await self.app(scope, receive, send)


class _SlidingLimiter:
    def __init__(self) -> None:
        self._eventos: dict[str, deque[float]] = {}
        self._lock = Lock()

    def permitir(self, clave: str, maximo: int, ventana: int) -> bool:
        ahora = time.monotonic()
        with self._lock:
            cola = self._eventos.setdefault(clave, deque())
            while cola and ahora - cola[0] > ventana:
                cola.popleft()
            if len(cola) >= maximo:
                return False
            cola.append(ahora)
            return True


_limiter = _SlidingLimiter()
_POLITICAS: tuple[tuple[str, str, int, int], ...] = (
    ("POST", "/api/auditar", 2, 60),
    ("POST", "/api/ventas", 30, 60),
    ("PUT", "/api/ventas/", 30, 60),
    ("GET", "/api/exportar/", 10, 60),
    ("GET", "/api/ventas", 60, 60),
    ("GET", "/ventas", 60, 60),
    ("GET", "/dashboard", 60, 60),
)


def _politica(metodo: str, ruta: str) -> tuple[int, int] | None:
    for metodo_politica, prefijo, maximo, ventana in _POLITICAS:
        if metodo == metodo_politica and ruta.startswith(prefijo):
            return maximo, ventana
    return None


class RateLimitMiddleware:
    """Rate limit simple en memoria para LAN de un proceso."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not RATE_LIMIT_ENABLED:
            await self.app(scope, receive, send)
            return
        politica = _politica(scope["method"], scope.get("path", ""))
        if politica is None:
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        ip = client[0] if client else "desconocido"
        maximo, ventana = politica
        if not _limiter.permitir(f"{ip}:{scope['method']}:{scope['path']}", maximo, ventana):
            response = JSONResponse(
                {"detail": "Demasiadas solicitudes. Esperá un momento."},
                status_code=429,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class RequestLoggingMiddleware:
    """Registra método, ruta y estado sin query string ni PII."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        estado = 500

        async def send_con_estado(message: Message) -> None:
            nonlocal estado
            if message["type"] == "http.response.start":
                estado = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_con_estado)
        finally:
            logger.info(
                "%s %s %s",
                scope["method"],
                scope.get("path", ""),
                estado,
            )
