"""Esquemas Pydantic v2 para validación y serialización de la API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from ventas_app.models import EstadoVenta, MedioPago, Parentesco, TarjetaMarca

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
NumeroTarjeta = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\d{16}$"),
]
VencimientoTarjeta = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^(0[1-9]|1[0-2])/\d{2}$",
    ),
]
Cvv = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\d{3,4}$"),
]
NumeroCbu = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\d{22}$"),
]
Cuil = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\d{11}$"),
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


class TarjetaIn(BaseModel):
    """Datos de tarjeta para validar; el CVV no se persiste."""

    model_config = ConfigDict(extra="forbid")

    marca: TarjetaMarca
    numero: NumeroTarjeta
    titular: Nombre
    vencimiento: VencimientoTarjeta
    cvv: Cvv

    @field_validator("vencimiento")
    @classmethod
    def validar_vencimiento(cls, valor: str) -> str:
        mes, anio = valor.split("/")
        hoy = date.today()
        if (2000 + int(anio), int(mes)) < (hoy.year, hoy.month):
            raise ValueError("La tarjeta está vencida.")
        return valor


class CbuIn(BaseModel):
    """Datos de CBU para validar y enmascarar."""

    model_config = ConfigDict(extra="forbid")

    numero: NumeroCbu
    entidad: Nombre
    titular: Nombre
    cuil: Cuil


class _VentaDatosIn(BaseModel):
    """Campos comunes para crear o actualizar un legajo."""

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
    medio_pago: MedioPago
    tarjeta: TarjetaIn | None = None
    cbu: CbuIn | None = None
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
    def validar_dnis_unicos(self) -> Self:
        dnis = [self.dni_titular, *(integrante.dni for integrante in self.integrantes)]
        duplicados = sorted({dni for dni in dnis if dnis.count(dni) > 1})
        if duplicados:
            raise ValueError(
                "Los DNIs del grupo familiar deben ser únicos. "
                f"Duplicados: {', '.join(duplicados)}."
            )
        return self


class VentaIn(_VentaDatosIn):
    """Payload de creación de una venta completa."""

    @model_validator(mode="after")
    def validar_instrumento_pago(self) -> Self:
        if self.medio_pago is MedioPago.TARJETA_CREDITO:
            if self.tarjeta is None:
                raise ValueError(
                    "Ingresá los datos de la tarjeta para el medio de pago "
                    "TARJETA_CREDITO."
                )
            if self.cbu is not None:
                raise ValueError("No envíes datos de CBU con tarjeta de crédito.")
        elif self.medio_pago is MedioPago.CBU:
            if self.cbu is None:
                raise ValueError(
                    "Ingresá los datos del CBU para el medio de pago CBU."
                )
            if self.tarjeta is not None:
                raise ValueError("No envíes datos de tarjeta con CBU.")
        elif self.tarjeta is not None or self.cbu is not None:
            raise ValueError(
                "El medio de pago seleccionado no admite datos de tarjeta ni CBU."
            )
        return self


class VentaUpdateIn(_VentaDatosIn):
    """Payload de edición; el instrumento puede omitirse para conservarlo."""

    @model_validator(mode="after")
    def validar_instrumento_opcional(self) -> Self:
        if self.tarjeta is not None and self.cbu is not None:
            raise ValueError("No envíes datos de tarjeta y CBU al mismo tiempo.")
        if self.tarjeta is not None and self.medio_pago is not MedioPago.TARJETA_CREDITO:
            raise ValueError("Solo podés enviar tarjeta con el medio TARJETA_CREDITO.")
        if self.cbu is not None and self.medio_pago is not MedioPago.CBU:
            raise ValueError("Solo podés enviar CBU con el medio CBU.")
        return self


class PlanOut(BaseModel):
    """Representación pública de un plan."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    precio_titular: int
    precio_adherente: int
    activo: bool


class TrazaMCPOut(BaseModel):
    """Una invocación registrada al servidor MCP."""

    herramienta: str
    argumentos: dict[str, Any]
    estado: str


class AuditoriaOut(BaseModel):
    """Resultado estructurado de una corrida del Agente Auditor."""

    procesadas: int
    aprobadas: int
    observadas: int
    resumen_llm: str | None = None
    llm_ok: bool
    advertencia: str | None = None
    traza_mcp: list[TrazaMCPOut]


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
    medio_pago: MedioPago
    subtotal_base: int
    descuento_porcentaje: int
    pago_titular: str | None
    pago_marca_entidad: str | None
    pago_ultimos_4: str | None
    pago_vencimiento: str | None
    pago_cuil: str | None
    precio_total: int
    estado: EstadoVenta
    observaciones: str | None
    integrantes: list[IntegranteOut]
    creado_en: datetime
    actualizado_en: datetime
