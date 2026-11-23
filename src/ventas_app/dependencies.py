"""Dependencias FastAPI de autenticación, CSRF y RBAC."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ventas_app.config import SESSION_COOKIE_NAME
from ventas_app.database import get_db
from ventas_app.models import RolUsuario, Sesion, Usuario
from ventas_app.security import (
    ahora_utc,
    comparar_hash,
    obtener_sesion_valida,
    registrar_evento_seguridad,
)

SessionDep = Annotated[Session, Depends(get_db)]
METODOS_CON_CSRF = {"POST", "PUT", "PATCH", "DELETE"}


def _token_sesion(request: Request) -> str:
    return request.cookies.get(SESSION_COOKIE_NAME, "")


def _denegar_web(request: Request) -> HTTPException:
    destino = quote(request.url.path or "/", safe="/")
    return HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Location": f"/login?next={destino}"},
        detail="Autenticación requerida.",
    )


async def _validar_csrf(request: Request, sesion: Sesion) -> None:
    if request.method not in METODOS_CON_CSRF:
        return
    token = request.headers.get("X-CSRF-Token", "")
    if not token:
        form = await request.form()
        token = str(form.get("csrf_token", ""))
    if not token or not comparar_hash(token, sesion.csrf_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token CSRF inválido.",
        )


async def require_web_user(
    request: Request,
    db: SessionDep,
) -> Usuario:
    sesion = obtener_sesion_valida(db, _token_sesion(request))
    if sesion is None:
        raise _denegar_web(request)
    await _validar_csrf(request, sesion)
    request.state.usuario = sesion.usuario
    request.state.sesion = sesion
    request.state.csrf_token = request.cookies.get("vos_csrf", "")
    sesion.ultimo_uso = ahora_utc()
    db.commit()
    return sesion.usuario


async def require_api_user(
    request: Request,
    db: SessionDep,
) -> Usuario:
    sesion = obtener_sesion_valida(db, _token_sesion(request))
    if sesion is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida.",
        )
    await _validar_csrf(request, sesion)
    request.state.usuario = sesion.usuario
    request.state.sesion = sesion
    request.state.csrf_token = request.cookies.get("vos_csrf", "")
    sesion.ultimo_uso = ahora_utc()
    db.commit()
    return sesion.usuario


async def require_mfa_pending(
    request: Request,
    db: SessionDep,
) -> tuple[Sesion, Usuario]:
    sesion = obtener_sesion_valida(
        db,
        _token_sesion(request),
        permitir_pendiente=True,
    )
    if sesion is None:
        raise _denegar_web(request)
    await _validar_csrf(request, sesion)
    request.state.usuario = None
    request.state.sesion = sesion
    request.state.csrf_token = request.cookies.get("vos_csrf", "")
    return sesion, sesion.usuario


def _roles(valores: tuple[RolUsuario, ...]) -> set[str]:
    return {rol.value for rol in valores}


def _registrar_denegacion(
    db: Session,
    request: Request,
    usuario: Usuario,
) -> None:
    registrar_evento_seguridad(
        db,
        tipo="ACCESO_DENEGADO",
        resultado="FALLO",
        usuario_id=usuario.id,
        ip=request.client.host if request.client else None,
        detalle=f"Ruta denegada: {request.url.path[:300]}",
    )
    db.commit()


def require_web_roles(*roles: RolUsuario) -> Callable:
    permitidos = _roles(roles)

    async def dependencia(
        request: Request,
        db: SessionDep,
        usuario: Annotated[Usuario, Depends(require_web_user)],
    ) -> Usuario:
        if usuario.rol not in permitidos:
            _registrar_denegacion(db, request, usuario)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permisos para esta acción.",
            )
        return usuario

    return dependencia


def require_api_roles(*roles: RolUsuario) -> Callable:
    permitidos = _roles(roles)

    async def dependencia(
        request: Request,
        db: SessionDep,
        usuario: Annotated[Usuario, Depends(require_api_user)],
    ) -> Usuario:
        if usuario.rol not in permitidos:
            _registrar_denegacion(db, request, usuario)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permisos para esta acción.",
            )
        return usuario

    return dependencia


__all__ = [
    "require_api_roles",
    "require_api_user",
    "require_mfa_pending",
    "require_web_roles",
    "require_web_user",
]
