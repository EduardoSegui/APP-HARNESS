"""Servicios de usuarios locales y bootstrap administrativo."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ventas_app.models import RolUsuario, Usuario
from ventas_app.security import (
    bloquear_usuario,
    hash_password,
    limpiar_bloqueo,
    revocar_sesiones_usuario,
    usuario_bloqueado,
    verificar_codigo_recuperacion,
    verify_password,
)


class UsuarioYaExisteError(ValueError):
    """El username ya está registrado."""


class CredencialesInvalidasError(ValueError):
    """Credenciales incorrectas; el mensaje al cliente debe ser genérico."""


class PasswordDebilError(ValueError):
    """La contraseña no cumple la política mínima."""


def normalizar_username(username: str) -> str:
    return username.strip().lower()


def validar_password(password: str) -> None:
    if len(password) < 12:
        raise PasswordDebilError(
            "La contraseña debe tener al menos 12 caracteres."
        )


def crear_usuario(
    db: Session,
    *,
    username: str,
    password: str,
    rol: RolUsuario,
    commit: bool = True,
) -> Usuario:
    username_normalizado = normalizar_username(username)
    if not username_normalizado or len(username_normalizado) > 50:
        raise ValueError("El usuario debe tener entre 1 y 50 caracteres.")
    validar_password(password)
    existe = db.scalar(
        select(Usuario).where(Usuario.username == username_normalizado)
    )
    if existe is not None:
        raise UsuarioYaExisteError("El usuario ya existe.")
    usuario = Usuario(
        username=username_normalizado,
        password_hash=hash_password(password),
        rol=rol.value,
    )
    db.add(usuario)
    if commit:
        db.commit()
        db.refresh(usuario)
    return usuario


def bootstrap_admin(
    db: Session,
    *,
    username: str,
    password: str,
) -> Usuario:
    if db.scalar(select(Usuario.id).where(Usuario.rol == RolUsuario.ADMIN.value)):
        raise UsuarioYaExisteError("Ya existe un administrador.")
    return crear_usuario(
        db,
        username=username,
        password=password,
        rol=RolUsuario.ADMIN,
    )


def obtener_por_username(db: Session, username: str) -> Usuario | None:
    return db.scalar(
        select(Usuario).where(
            Usuario.username == normalizar_username(username)
        )
    )


def verificar_credenciales(
    db: Session,
    *,
    username: str,
    password: str,
) -> Usuario:
    """Verifica usuario/contraseña y bloquea tras intentos fallidos."""
    usuario = obtener_por_username(db, username)
    if usuario is None or not usuario.activo or usuario_bloqueado(usuario):
        raise CredencialesInvalidasError("Credenciales inválidas.")

    if not verify_password(usuario.password_hash, password):
        bloquear_usuario(usuario)
        db.commit()
        raise CredencialesInvalidasError("Credenciales inválidas.")

    return usuario


def autenticar(
    db: Session,
    *,
    username: str,
    password: str,
    codigo_mfa: str | None = None,
) -> Usuario:
    """Valida credenciales y MFA si está habilitado."""
    usuario = verificar_credenciales(
        db,
        username=username,
        password=password,
    )

    if usuario.mfa_enabled:
        if not codigo_mfa:
            raise CredencialesInvalidasError("Se requiere código MFA.")
        if not verificar_codigo_recuperacion(db, usuario, codigo_mfa):
            from ventas_app.security import (
                descifrar_secreto,
                verificar_totp,
            )

            try:
                secreto = descifrar_secreto(usuario.mfa_secret_enc or "")
            except ValueError as exc:
                raise CredencialesInvalidasError("MFA inválido.") from exc
            contador = verificar_totp(
                secreto,
                codigo_mfa,
                ultimo_contador=usuario.mfa_last_counter,
            )
            if contador is None:
                bloquear_usuario(usuario)
                db.commit()
                raise CredencialesInvalidasError("MFA inválido.")
            usuario.mfa_last_counter = contador

    limpiar_bloqueo(usuario)
    db.commit()
    return usuario


def resetear_password(db: Session, usuario: Usuario, password: str) -> None:
    validar_password(password)
    usuario.password_hash = hash_password(password)
    limpiar_bloqueo(usuario)
    revocar_sesiones_usuario(db, usuario.id)
    db.commit()


def desactivar_usuario(db: Session, usuario: Usuario) -> None:
    usuario.activo = False
    revocar_sesiones_usuario(db, usuario.id)
    db.commit()


def activar_usuario(db: Session, usuario: Usuario) -> None:
    usuario.activo = True
    db.commit()


__all__ = [
    "CredencialesInvalidasError",
    "PasswordDebilError",
    "UsuarioYaExisteError",
    "activar_usuario",
    "autenticar",
    "bootstrap_admin",
    "crear_usuario",
    "desactivar_usuario",
    "normalizar_username",
    "obtener_por_username",
    "resetear_password",
    "validar_password",
    "verificar_credenciales",
]
