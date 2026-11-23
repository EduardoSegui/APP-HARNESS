"""Cifrado simétrico de campos sensibles con Fernet."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from ventas_app.config import APP_ENCRYPTION_KEY


class EncryptionKeyError(RuntimeError):
    """Falta una clave válida para cifrar datos sensibles."""


def _fernet() -> Fernet:
    if not APP_ENCRYPTION_KEY:
        raise EncryptionKeyError(
            "Falta APP_ENCRYPTION_KEY; es obligatoria para datos sensibles."
        )
    try:
        return Fernet(APP_ENCRYPTION_KEY.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise EncryptionKeyError(
            "APP_ENCRYPTION_KEY no es una clave Fernet válida."
        ) from exc


def _fernet_para(clave: str) -> Fernet:
    if not clave:
        raise EncryptionKeyError("Falta una clave de cifrado.")
    try:
        return Fernet(clave.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise EncryptionKeyError(
            "La clave de cifrado no es una clave Fernet válida."
        ) from exc


def cifrar_texto(valor: str) -> str:
    return _fernet().encrypt(valor.encode("utf-8")).decode("ascii")


def descifrar_texto(valor: str) -> str:
    try:
        return _fernet().decrypt(valor.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("No se pudo descifrar el campo sensible.") from exc


def cifrar_bytes(datos: bytes, clave: str) -> bytes:
    return _fernet_para(clave).encrypt(datos)


def descifrar_bytes(datos: bytes, clave: str) -> bytes:
    try:
        return _fernet_para(clave).decrypt(datos)
    except (InvalidToken, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("No se pudo descifrar el backup.") from exc


def es_token_cifrado(valor: str) -> bool:
    """Reconoce la forma de un token Fernet sin autenticarlo."""
    return isinstance(valor, str) and valor.startswith("gAAAA") and len(valor) > 80


def es_token_valido(valor: str) -> bool:
    """Indica si el valor es un token auténtico con la clave actual."""
    if not es_token_cifrado(valor) or not clave_disponible():
        return False
    try:
        descifrar_texto(valor)
    except ValueError:
        return False
    return True


def clave_disponible() -> bool:
    """Indica si el proceso tiene una clave de campos configurada."""
    return bool(APP_ENCRYPTION_KEY)


__all__ = [
    "EncryptionKeyError",
    "cifrar_bytes",
    "cifrar_texto",
    "clave_disponible",
    "descifrar_bytes",
    "descifrar_texto",
    "es_token_cifrado",
    "es_token_valido",
]
