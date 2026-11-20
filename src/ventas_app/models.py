"""Modelos ORM de la aplicación de ventas de obra social."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ventas_app.database import Base


class EstadoVenta(str, Enum):
    """Estados posibles de una venta."""

    PENDIENTE_VERIFICACION = "PENDIENTE_VERIFICACION"
    APROBADA = "APROBADA"
    OBSERVADA = "OBSERVADA"


class MedioPago(str, Enum):
    """Medios de pago admitidos para la contratación."""

    TARJETA_CREDITO = "TARJETA_CREDITO"
    CBU = "CBU"
    PAGO_FACIL = "PAGO_FACIL"
    COBRADOR_DOMICILIO = "COBRADOR_DOMICILIO"


class TarjetaMarca(str, Enum):
    """Marcas de tarjeta admitidas en el alta."""

    VISA = "VISA"
    MASTERCARD = "MASTERCARD"
    AMEX = "AMEX"
    CABAL = "CABAL"


class RegimenAfiliacion(str, Enum):
    """Régimen comercial del afiliado."""

    PARTICULAR = "PARTICULAR"
    RELACION_DEPENDENCIA = "RELACION_DEPENDENCIA"
    MONOTRIBUTO = "MONOTRIBUTO"


class Parentesco(str, Enum):
    """Parentescos admitidos para los integrantes del grupo familiar."""

    CONYUGE_PAREJA = "Cónyuge/Pareja"
    HIJO_A = "Hijo/a"
    NIETO_A = "Nieto/a"
    SOBRINO_A = "Sobrino/a"
    FAMILIAR_A_CARGO = "Familiar a cargo"
    AMIGO_OTRO = "Amigo/Otro"


_ESTADOS_SQL = ", ".join(f"'{estado.value}'" for estado in EstadoVenta)
_MEDIOS_PAGO_SQL = ", ".join(f"'{medio.value}'" for medio in MedioPago)
_PARENTESCOS_SQL = ", ".join(f"'{parentesco.value}'" for parentesco in Parentesco)


def _utcnow() -> datetime:
    """Devuelve la fecha/hora actual en UTC."""
    return datetime.now(timezone.utc)


class Plan(Base):
    """Plan de cobertura y precios vigentes."""

    __tablename__ = "planes"
    __table_args__ = (
        CheckConstraint(
            "precio_titular > 0",
            name="ck_planes_precio_titular_positivo",
        ),
        CheckConstraint(
            "precio_adherente >= 0",
            name="ck_planes_precio_adherente_no_negativo",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    precio_titular: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_adherente: Mapped[int] = mapped_column(Integer, nullable=False)
    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )

    ventas: Mapped[list[Venta]] = relationship(back_populates="plan")


class Venta(Base):
    """Venta registrada por el operador comercial."""

    __tablename__ = "ventas"
    __table_args__ = (
        CheckConstraint(
            "precio_total >= 0",
            name="ck_ventas_precio_total_no_negativo",
        ),
        CheckConstraint(
            f"estado IN ({_ESTADOS_SQL})",
            name="ck_ventas_estado_valido",
        ),
        CheckConstraint(
            f"medio_pago IN ({_MEDIOS_PAGO_SQL})",
            name="ck_ventas_medio_pago_valido",
        ),
        CheckConstraint("subtotal_base >= 0", name="ck_ventas_subtotal_base_no_negativo"),
        CheckConstraint("descuento_porcentaje >= 0", name="ck_ventas_descuento_no_negativo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    nombre_titular: Mapped[str] = mapped_column(String(80), nullable=False)
    apellido_titular: Mapped[str] = mapped_column(String(80), nullable=False)
    dni_titular: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    fecha_nacimiento_titular: Mapped[date] = mapped_column(Date, nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    telefono: Mapped[str] = mapped_column(String(25), nullable=False)

    calle: Mapped[str] = mapped_column(String(120), nullable=False)
    altura: Mapped[str] = mapped_column(String(10), nullable=False)
    piso_depto: Mapped[str | None] = mapped_column(String(30), nullable=True)
    localidad: Mapped[str] = mapped_column(String(80), nullable=False)
    provincia: Mapped[str] = mapped_column(String(80), nullable=False)
    codigo_postal: Mapped[str] = mapped_column(String(4), nullable=False)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("planes.id"),
        nullable=False,
        index=True,
    )
    medio_pago: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=MedioPago.PAGO_FACIL.value,
        server_default=text(f"'{MedioPago.PAGO_FACIL.value}'"),
    )
    subtotal_base: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    descuento_porcentaje: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    pago_titular: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pago_marca_entidad: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )
    pago_ultimos_4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    pago_vencimiento: Mapped[str | None] = mapped_column(String(5), nullable=True)
    pago_cuil: Mapped[str | None] = mapped_column(String(11), nullable=True)
    ddjj_completada: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    ddjj_preexistencias: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    ddjj_internaciones: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    ddjj_embarazo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    ddjj_medicacion_cronica: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    ddjj_discapacidad: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    ddjj_detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    regimen_afiliacion: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=RegimenAfiliacion.PARTICULAR.value,
        server_default=text(f"'{RegimenAfiliacion.PARTICULAR.value}'"),
    )
    cuil_titular: Mapped[str | None] = mapped_column(String(11), nullable=True)
    aporte_estimado: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    precio_total: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=EstadoVenta.PENDIENTE_VERIFICACION.value,
        server_default=text(f"'{EstadoVenta.PENDIENTE_VERIFICACION.value}'"),
        index=True,
    )
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    plan: Mapped[Plan] = relationship(back_populates="ventas")
    integrantes: Mapped[list[Integrante]] = relationship(
        back_populates="venta",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Integrante.id",
    )


class Integrante(Base):
    """Adherente del grupo familiar de una venta."""

    __tablename__ = "integrantes"
    __table_args__ = (
        UniqueConstraint("venta_id", "dni", name="uq_integrantes_venta_dni"),
        CheckConstraint(
            f"parentesco IN ({_PARENTESCOS_SQL})",
            name="ck_integrantes_parentesco_valido",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venta_id: Mapped[int] = mapped_column(
        ForeignKey("ventas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    apellido: Mapped[str] = mapped_column(String(80), nullable=False)
    dni: Mapped[str] = mapped_column(String(8), nullable=False)
    fecha_nacimiento: Mapped[date] = mapped_column(Date, nullable=False)
    parentesco: Mapped[str] = mapped_column(String(30), nullable=False)

    venta: Mapped[Venta] = relationship(back_populates="integrantes")
