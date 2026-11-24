"""Rutas de login, MFA y logout."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ventas_app.config import (
    MFA_ISSUER,
    MFA_MAX_FAILED_ATTEMPTS,
    SESSION_ABSOLUTE_HOURS,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SECURE,
)
from ventas_app.database import get_db
from ventas_app.dependencies import require_mfa_pending, require_web_user
from ventas_app.models import CodigoRecuperacion, RolUsuario, Sesion, Usuario
from ventas_app.security import (
    ahora_utc,
    cifrar_secreto,
    crear_sesion,
    descifrar_secreto,
    generar_codigos_recuperacion,
    generar_secreto_totp,
    hash_password,
    limpiar_bloqueo,
    login_rate_limiter,
    mfa_rate_limiter,
    registrar_evento_seguridad,
    revocar_sesion,
    verificar_codigo_recuperacion,
    verificar_totp,
)
from ventas_app.services.usuarios import (
    CredencialesInvalidasError,
    verificar_credenciales,
)

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _destino_seguro(valor: str | None) -> str:
    if not valor or not valor.startswith("/") or valor.startswith("//"):
        return "/"
    return valor


def _set_cookies(
    respuesta,
    *,
    token: str,
    csrf: str,
    autenticada: bool,
) -> None:
    max_age = SESSION_ABSOLUTE_HOURS * 3600 if autenticada else 600
    respuesta.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    respuesta.set_cookie(
        "vos_csrf",
        csrf,
        max_age=max_age,
        httponly=False,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _login_csrf(request: Request) -> str:
    return request.cookies.get("login_csrf", "")


@router.get("/login")
def mostrar_login(
    request: Request,
    next: str | None = None,
    db: Session = Depends(get_db),
):
    from ventas_app.security import obtener_sesion_valida

    if obtener_sesion_valida(
        db,
        request.cookies.get(SESSION_COOKIE_NAME, ""),
    ):
        return RedirectResponse(
            url=_destino_seguro(next),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    token = _login_csrf(request) or ""
    if not token:
        import secrets

        token = secrets.token_urlsafe(32)
    respuesta = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "csrf_token": token,
            "next": _destino_seguro(next),
            "error": None,
        },
    )
    respuesta.set_cookie(
        "login_csrf",
        token,
        max_age=600,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return respuesta


@router.post("/login")
def iniciar_sesion(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()] = "",
    next: Annotated[str, Form()] = "/",
    db: Session = Depends(get_db),
):
    if not csrf_token or csrf_token != _login_csrf(request):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": _login_csrf(request),
                "next": _destino_seguro(next),
                "error": "Solicitud inválida.",
            },
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if not login_rate_limiter.permitir(f"{_ip(request)}:{username.lower()}"):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": _login_csrf(request),
                "next": _destino_seguro(next),
                "error": "Demasiados intentos. Esperá un minuto.",
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    try:
        usuario = verificar_credenciales(
            db,
            username=username,
            password=password,
        )
    except CredencialesInvalidasError:
        registrar_evento_seguridad(
            db,
            tipo="LOGIN",
            resultado="FALLO",
            ip=_ip(request),
        )
        db.commit()
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": _login_csrf(request),
                "next": _destino_seguro(next),
                "error": "Usuario o contraseña incorrectos.",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    requiere_mfa = usuario.rol in (RolUsuario.ADMIN.value, RolUsuario.AUDITOR.value)
    if usuario.mfa_enabled or requiere_mfa:
        token, csrf, _ = crear_sesion(
            db,
            usuario,
            ip=_ip(request),
            user_agent=request.headers.get("user-agent"),
            autenticada=False,
        )
        db.commit()
        destino = f"/mfa?next={quote(_destino_seguro(next), safe='/')}"
        respuesta = RedirectResponse(
            url=destino,
            status_code=status.HTTP_303_SEE_OTHER,
        )
        _set_cookies(respuesta, token=token, csrf=csrf, autenticada=False)
        return respuesta

    token, csrf, _ = crear_sesion(
        db,
        usuario,
        ip=_ip(request),
        user_agent=request.headers.get("user-agent"),
        autenticada=True,
    )
    usuario.last_login = ahora_utc()
    limpiar_bloqueo(usuario)
    registrar_evento_seguridad(
        db,
        tipo="LOGIN",
        resultado="OK",
        usuario_id=usuario.id,
        ip=_ip(request),
    )
    db.commit()
    respuesta = RedirectResponse(
        url=_destino_seguro(next),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _set_cookies(respuesta, token=token, csrf=csrf, autenticada=True)
    return respuesta


@router.get("/mfa")
def mostrar_mfa(
    request: Request,
    next: str | None = None,
    sesion_usuario: tuple[Sesion, Usuario] = Depends(require_mfa_pending),
    db: Session = Depends(get_db),
):
    sesion, usuario = sesion_usuario
    if usuario.mfa_enabled:
        return templates.TemplateResponse(
            request=request,
            name="mfa.html",
            context={
                "modo_setup": False,
                "csrf_token": request.cookies.get("vos_csrf", ""),
                "next": _destino_seguro(next),
                "error": None,
            },
        )

    if not usuario.mfa_secret_enc:
        secreto = generar_secreto_totp()
        usuario.mfa_secret_enc = cifrar_secreto(secreto)
        for codigo in db.scalars(
            select(CodigoRecuperacion).where(
                CodigoRecuperacion.usuario_id == usuario.id
            )
        ):
            db.delete(codigo)
        codigos = generar_codigos_recuperacion()
        for codigo in codigos:
            db.add(
                CodigoRecuperacion(
                    usuario_id=usuario.id,
                    codigo_hash=hash_password(codigo),
                )
            )
        db.commit()
    else:
        secreto = descifrar_secreto(usuario.mfa_secret_enc)
        codigos = []

    uri = (
        "otpauth://totp/"
        f"{quote(MFA_ISSUER)}:{quote(usuario.username)}"
        f"?secret={secreto}&issuer={quote(MFA_ISSUER)}"
    )
    return templates.TemplateResponse(
        request=request,
        name="mfa.html",
        context={
            "modo_setup": True,
            "secreto": secreto,
            "otpauth": uri,
            "codigos": codigos,
            "csrf_token": request.cookies.get("vos_csrf", ""),
            "next": _destino_seguro(next),
            "error": None,
        },
    )


def _registrar_fallo_mfa(
    db: Session,
    sesion: Sesion,
    usuario: Usuario,
    request: Request,
) -> None:
    """Incrementa intentos, revoca la sesión pendiente y audita sin PII."""
    sesion.mfa_failed_attempts = (sesion.mfa_failed_attempts or 0) + 1
    if sesion.mfa_failed_attempts >= MFA_MAX_FAILED_ATTEMPTS:
        revocar_sesion(db, sesion)
    registrar_evento_seguridad(
        db,
        tipo="MFA",
        resultado="FALLO",
        usuario_id=usuario.id,
        ip=_ip(request),
        detalle="Intento de código MFA inválido.",
    )
    db.commit()


@router.post("/mfa")
def confirmar_mfa(
    request: Request,
    codigo: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/",
    sesion_usuario: tuple[Sesion, Usuario] = Depends(require_mfa_pending),
    db: Session = Depends(get_db),
):
    sesion, usuario = sesion_usuario
    if not mfa_rate_limiter.permitir(
        f"mfa:{_ip(request)}:{usuario.id}"
    ):
        registrar_evento_seguridad(
            db,
            tipo="MFA",
            resultado="RATE_LIMIT",
            usuario_id=usuario.id,
            ip=_ip(request),
        )
        db.commit()
        return templates.TemplateResponse(
            request=request,
            name="mfa.html",
            context={
                "modo_setup": not usuario.mfa_enabled,
                "csrf_token": request.cookies.get("vos_csrf", ""),
                "next": _destino_seguro(next),
                "error": "Demasiados intentos. Esperá un minuto.",
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    if not usuario.mfa_enabled:
        try:
            secreto = descifrar_secreto(usuario.mfa_secret_enc or "")
        except ValueError:
            _registrar_fallo_mfa(db, sesion, usuario, request)
            return templates.TemplateResponse(
                request=request,
                name="mfa.html",
                context={
                    "modo_setup": True,
                    "csrf_token": request.cookies.get("vos_csrf", ""),
                    "next": _destino_seguro(next),
                    "error": "No se pudo iniciar MFA. Volvé a intentar.",
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        contador = verificar_totp(
            secreto,
            codigo.strip(),
            ultimo_contador=usuario.mfa_last_counter,
        )
        if contador is None:
            _registrar_fallo_mfa(db, sesion, usuario, request)
            return templates.TemplateResponse(
                request=request,
                name="mfa.html",
                context={
                    "modo_setup": True,
                    "secreto": secreto,
                    "csrf_token": request.cookies.get("vos_csrf", ""),
                    "next": _destino_seguro(next),
                    "error": "Código inválido.",
                },
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        usuario.mfa_enabled = True
        usuario.mfa_last_counter = contador
        registrar_evento_seguridad(
            db,
            tipo="MFA_SETUP",
            resultado="OK",
            usuario_id=usuario.id,
            ip=_ip(request),
        )
    else:
        valido = False
        try:
            secreto = descifrar_secreto(usuario.mfa_secret_enc or "")
            contador = verificar_totp(
                secreto,
                codigo.strip(),
                ultimo_contador=usuario.mfa_last_counter,
            )
            if contador is not None:
                usuario.mfa_last_counter = contador
                valido = True
        except ValueError:
            pass
        if not valido:
            valido = verificar_codigo_recuperacion(db, usuario, codigo)
        if not valido:
            _registrar_fallo_mfa(db, sesion, usuario, request)
            return templates.TemplateResponse(
                request=request,
                name="mfa.html",
                context={
                    "modo_setup": False,
                    "csrf_token": request.cookies.get("vos_csrf", ""),
                    "next": _destino_seguro(next),
                    "error": "Código inválido.",
                },
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

    usuario.last_login = ahora_utc()
    limpiar_bloqueo(usuario)
    token, csrf, _ = crear_sesion(
        db,
        usuario,
        ip=_ip(request),
        user_agent=request.headers.get("user-agent"),
        autenticada=True,
    )
    revocar_sesion(db, sesion)
    registrar_evento_seguridad(
        db,
        tipo="LOGIN_MFA",
        resultado="OK",
        usuario_id=usuario.id,
        ip=_ip(request),
    )
    db.commit()
    respuesta = RedirectResponse(
        url=_destino_seguro(next),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _set_cookies(respuesta, token=token, csrf=csrf, autenticada=True)
    return respuesta


@router.post("/logout")
def cerrar_sesion(
    request: Request,
    usuario: Usuario = Depends(require_web_user),
    db: Session = Depends(get_db),
):
    sesion = request.state.sesion
    revocar_sesion(db, sesion)
    registrar_evento_seguridad(
        db,
        tipo="LOGOUT",
        resultado="OK",
        usuario_id=usuario.id,
        ip=_ip(request),
    )
    db.commit()
    respuesta = RedirectResponse(
        url="/login",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    respuesta.delete_cookie(SESSION_COOKIE_NAME, path="/")
    respuesta.delete_cookie("vos_csrf", path="/")
    return respuesta


__all__ = ["router"]
