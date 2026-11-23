"""Primitivas de seguridad: contraseñas, sesiones, CSRF, TOTP y secretos."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError, VerificationError
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from ventas_app.config import (
    APP_ENCRYPTION_KEY,
    LOGIN_LOCK_MINUTES,
    LOGIN_RATE_MAX_ATTEMPTS,
    LOGIN_RATE_WINDOW_SECONDS,
    SESSION_ABSOLUTE_HOURS,
    SESSION_COOKIE_NAME,
    SESSION_IDLE_MINUTES,
)
from ventas_app.models import CodigoRecuperacion, SecurityEvent, Sesion, Usuario

_PASSWORD_HASHER = PasswordHasher()
_TOTP_PERIOD = 30
_TOTP_DIGITS = 6


def ahora_utc() -> datetime:
    """UTC naive, consistente con SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def necesita_rehash(password_hash: str) -> bool:
    try:
        return _PASSWORD_HASHER.check_needs_rehash(password_hash)
    except (InvalidHash, VerificationError):
        return True


def generar_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def comparar_hash(token: str, hash_guardado: str) -> bool:
    return hmac.compare_digest(hash_token(token), hash_guardado)


def _fernet() -> Fernet:
    if not APP_ENCRYPTION_KEY:
        raise RuntimeError(
            "Falta APP_ENCRYPTION_KEY; es obligatoria para MFA."
        )
    return Fernet(APP_ENCRYPTION_KEY.encode("ascii"))


def cifrar_secreto(valor: str) -> str:
    return _fernet().encrypt(valor.encode("utf-8")).decode("ascii")


def descifrar_secreto(valor: str) -> str:
    try:
        return _fernet().decrypt(valor.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("No se pudo descifrar el secreto MFA.") from exc


def generar_secreto_totp() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _codigo_totp(secreto: str, contador: int) -> str:
    padding = "=" * ((8 - len(secreto) % 8) % 8)
    key = base64.b32decode(secreto + padding)
    digest = hmac.new(
        key,
        struct.pack(">Q", contador),
        hashlib.sha1,
    ).digest()
    offset = digest[-1] & 0x0F
    codigo = (
        struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    ) % (10**_TOTP_DIGITS)
    return f"{codigo:0{_TOTP_DIGITS}d}"


def verificar_totp(
    secreto: str,
    codigo: str,
    *,
    ultimo_contador: int | None = None,
    ahora: datetime | None = None,
) -> int | None:
    """Devuelve el contador aceptado, o None. Evita replay."""
    if not codigo.isdigit() or len(codigo) != _TOTP_DIGITS:
        return None
    referencia = ahora or datetime.now(timezone.utc)
    contador_actual = int(referencia.timestamp()) // _TOTP_PERIOD
    for delta in (-1, 0, 1):
        contador = contador_actual + delta
        if hmac.compare_digest(_codigo_totp(secreto, contador), codigo):
            if ultimo_contador is not None and contador <= ultimo_contador:
                return None
            return contador
    return None


def generar_codigos_recuperacion(cantidad: int = 10) -> list[str]:
    return [secrets.token_hex(4) for _ in range(cantidad)]


def crear_sesion(
    db: Session,
    usuario: Usuario,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    autenticada: bool = False,
    minutos: int | None = None,
) -> tuple[str, str, Sesion]:
    """Crea una sesión y devuelve (token, csrf, fila). No hace commit."""
    token = generar_token()
    csrf = generar_token()
    ahora = ahora_utc()
    if minutos is None:
        minutos = (
            SESSION_ABSOLUTE_HOURS * 60
            if autenticada
            else 10
        )
    sesion = Sesion(
        usuario_id=usuario.id,
        token_hash=hash_token(token),
        csrf_hash=hash_token(csrf),
        autenticada=autenticada,
        creado_en=ahora,
        ultimo_uso=ahora,
        expira_en=ahora + timedelta(minutes=minutos),
        ip=ip,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(sesion)
    return token, csrf, sesion


def obtener_sesion_valida(
    db: Session,
    token: str,
    *,
    permitir_pendiente: bool = False,
    ahora: datetime | None = None,
) -> Sesion | None:
    if not token:
        return None
    referencia = ahora or ahora_utc()
    sesion = db.scalar(
        select(Sesion).where(Sesion.token_hash == hash_token(token))
    )
    if sesion is None or sesion.revocada_en is not None:
        return None
    if sesion.expira_en <= referencia:
        return None
    if not permitir_pendiente and not sesion.autenticada:
        return None
    if referencia - sesion.ultimo_uso > timedelta(minutes=SESSION_IDLE_MINUTES):
        sesion.revocada_en = referencia
        return None
    if not sesion.usuario.activo:
        return None
    return sesion


def revocar_sesion(db: Session, sesion: Sesion) -> None:
    sesion.revocada_en = ahora_utc()


def revocar_sesiones_usuario(db: Session, usuario_id: int) -> None:
    for sesion in db.scalars(
        select(Sesion).where(
            Sesion.usuario_id == usuario_id,
            Sesion.revocada_en.is_(None),
        )
    ):
        sesion.revocada_en = ahora_utc()


def verificar_codigo_recuperacion(
    db: Session,
    usuario: Usuario,
    codigo: str,
) -> bool:
    if not codigo.strip():
        return False
    for fila in db.scalars(
        select(CodigoRecuperacion).where(
            CodigoRecuperacion.usuario_id == usuario.id,
            CodigoRecuperacion.usado_en.is_(None),
        )
    ):
        if verify_password(fila.codigo_hash, codigo.strip()):
            fila.usado_en = ahora_utc()
            return True
    return False


def registrar_evento_seguridad(
    db: Session,
    *,
    tipo: str,
    resultado: str,
    usuario_id: int | None = None,
    ip: str | None = None,
    request_id: str | None = None,
    detalle: str | None = None,
) -> None:
    db.add(
        SecurityEvent(
            tipo=tipo[:50],
            resultado=resultado[:20],
            usuario_id=usuario_id,
            ip=ip[:45] if ip else None,
            request_id=request_id[:64] if request_id else None,
            detalle=detalle[:1000] if detalle else None,
        )
    )


class _RateLimiter:
    def __init__(self) -> None:
        self._eventos: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def permitir(self, clave: str) -> bool:
        ahora = time.monotonic()
        with self._lock:
            cola = self._eventos.setdefault(clave, deque())
            while cola and ahora - cola[0] > LOGIN_RATE_WINDOW_SECONDS:
                cola.popleft()
            if len(cola) >= LOGIN_RATE_MAX_ATTEMPTS:
                return False
            cola.append(ahora)
            return True

    def limpiar(self) -> None:
        with self._lock:
            self._eventos.clear()


login_rate_limiter = _RateLimiter()


def bloquear_usuario(usuario: Usuario) -> None:
    usuario.failed_attempts += 1
    if usuario.failed_attempts >= 5:
        usuario.locked_until = ahora_utc() + timedelta(
            minutes=LOGIN_LOCK_MINUTES
        )


def usuario_bloqueado(usuario: Usuario, ahora: datetime | None = None) -> bool:
    if usuario.locked_until is None:
        return False
    return usuario.locked_until > (ahora or ahora_utc())


def limpiar_bloqueo(usuario: Usuario) -> None:
    usuario.failed_attempts = 0
    usuario.locked_until = None


def context_seguridad(usuario: Usuario | None, csrf: str | None = None) -> dict[str, Any]:
    """Contexto mínimo para templates; nunca incluye secretos."""
    return {"usuario": usuario, "csrf_token": csrf}
