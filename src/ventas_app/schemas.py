"""Esquemas Pydantic v2 para validación y serialización de la API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from ventas_app.models import EstadoVenta, Parentesco

_EMAIL_REGEX = (
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)

Nombre = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=80),
]
Dni = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\d{7,8}$"),
]
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=254,
        pattern=_EMAIL_REGEX,
    ),
]
Telefono = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=6,
        max_length=25,
        pattern=r"^[0-9+\s()\-]+$",
    ),
]
Calle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=120),
]
Altura = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=10,
        pattern=r"^[0-9A-Za-z/ .-]+$",
    ),
]
Localidad = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=80),
]
Provincia = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=80),
]
CodigoPostal = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\d{4}$"),
]
PisoDepto = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=30),
]


def _validar_fecha_no_futura(valor: date) -> date:
    if valor > date.today():
        raise ValueError("La fecha de nacimiento no puede ser futura.")
    return valor


def _validar_telefono_con_digitos(valor: str) -> str:
    if sum(caracter.isdigit() for caracter in valor) < 6:
        raise ValueError("El teléfono debe contener al menos 6 dígitos.")
    return valor


class IntegranteIn(BaseModel):
    """Datos de entrada de un adherente."""

    model_config = ConfigDict(extra="forbid")

    nombre: Nombre
    apellido: Nombre
    dni: Dni
    fecha_nacimiento: date
    parentesco: Parentesco

    @field_validator("fecha_nacimiento")
    @classmethod
    def validar_fecha(cls, valor: date) -> date:
        return _validar_fecha_no_futura(valor)


class VentaIn(BaseModel):
    """Payload de creación de una venta completa."""

    model_config = ConfigDict(extra="forbid")

    nombre_titular: Nombre
    apellido_titular: Nombre
    dni_titular: Dni
    fecha_nacimiento_titular: date
    email: Email
    telefono: Telefono

    calle: Calle
    altura: Altura
    piso_depto: PisoDepto | None = None
    localidad: Localidad
    provincia: Provincia
    codigo_postal: CodigoPostal

    plan_id: int = Field(gt=0)
    integrantes: list[IntegranteIn] = Field(default_factory=list)

    @field_validator("fecha_nacimiento_titular")
    @classmethod
    def validar_fecha_titular(cls, valor: date) -> date:
        return _validar_fecha_no_futura(valor)

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, valor: str) -> str:
        return _validar_telefono_con_digitos(valor)

    @field_validator("piso_depto", mode="before")
    @classmethod
    def normalizar_piso_depto(cls, valor: object) -> object:
        if isinstance(valor, str) and not valor.strip():
            return None
        return valor

    @model_validator(mode="after")
    def validar_dnis_unicos(self) -> VentaIn:
        dnis = [self.dni_titular, *(integrante.dni for integrante in self.integrantes)]
        duplicados = sorted({dni for dni in dnis if dnis.count(dni) > 1})
        if duplicados:
            raise ValueError(
                "Los DNIs del grupo familiar deben ser únicos. "
                f"Duplicados: {', '.join(duplicados)}."
            )
        return self


class PlanOut(BaseModel):
    """Representación pública de un plan."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    precio_titular: int
    precio_adherente: int
    activo: bool


class IntegranteOut(BaseModel):
    """Representación pública de un adherente persistido."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    venta_id: int
    nombre: str
    apellido: str
    dni: str
    fecha_nacimiento: date
    parentesco: Parentesco


class VentaOut(BaseModel):
    """Representación pública de una venta persistida."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_titular: str
    apellido_titular: str
    dni_titular: str
    fecha_nacimiento_titular: date
    email: str
    telefono: str
    calle: str
    altura: str
    piso_depto: str | None
    localidad: str
    provincia: str
    codigo_postal: str
    plan_id: int
    plan: PlanOut
    precio_total: int
    estado: EstadoVenta
    observaciones: str | None
    integrantes: list[IntegranteOut]
    creado_en: datetime
    actualizado_en: datetime
