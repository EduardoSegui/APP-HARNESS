"""Redacción de PII para eventos y logs internos."""

from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# DNI/CUIL, teléfonos y otros identificadores numéricos.
_NUMEROS = re.compile(r"\b\d{4,}\b")
# Solo teléfonos con separadores; un DNI/CUIL continuo se redacta como ***.
_TELEFONO = re.compile(r"(?<!\d)(?:\+?\d[\s().-]){4,}\d(?!\d)")


def redactar_pii(texto: str | None) -> str | None:
    """Oculta identificadores sin eliminar códigos de regla ni texto útil."""
    if not texto:
        return texto
    resultado = _EMAIL.sub("[email]", texto)
    resultado = _TELEFONO.sub("[telefono]", resultado)
    resultado = _NUMEROS.sub("***", resultado)
    return resultado


__all__ = ["redactar_pii"]
