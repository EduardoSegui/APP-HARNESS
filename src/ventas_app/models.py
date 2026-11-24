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
    TypeDecorator,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ventas_app.crypto import (
    cifrar_texto,
    clave_disponible,
    descifrar_texto,
    es_token_cifrado,
    es_token_valido,
)
from ventas_app.database import Base


class EstadoVenta(str, Enum):
    """Estados posibles de una venta."""

    PENDIENTE_VERIFICACION = "PENDIENTE_VERIFICACION"
    APROBADA = "APROBADA"
    OBSERVADA = "OBSERVADA"


class TipoEventoVenta(str, Enum):
    """Hitos inmutables del linaje de una venta."""

    CREADA = "CREADA"
    EDITADA = "EDITADA"
    AUDITADA_APROBADA = "AUDITADA_APROBADA"
    AUDITADA_OBSERVADA = "AUDITADA_OBSERVADA"


class RolUsuario(str, Enum):
    """Roles de acceso a la aplicación."""

    OPERADOR = "OPERADOR"
    AUDITOR = "AUDITOR"
    ADMIN = "ADMIN"


class EncryptedText(TypeDecorator[str]):
    """Texto cifrado en reposo; tolera filas históricas en texto plano."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        # No confiar en el prefijo: si no es un token auténtico, se cifra.
        if es_token_valido(value):
            return value
        return cifrar_texto(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        if not clave_disponible():
            # Un subproceso sin clave (MCP) no puede leer salud; solo su
            # presencia. Tampoco debe exponer filas históricas en claro.
            return "[cifrado]"
        if not es_token_cifrado(value):
            # Compatibilidad de lectura con filas históricas en texto plano.
            return value
        try:
            return descifrar_texto(value)
        except ValueError as exc:
            raise ValueError(
                "El dato cifrado no pertenece a la clave activa o está "
                "corrupto; no se re-cifra automáticamente."
            ) from exc


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
_ROLES_SQL = ", ".join(f"'{rol.value}'" for rol in RolUsuario)
_TIPOS_EVENTO_SQL = ", ".join(
    f"'{tipo.value}'" for tipo in TipoEventoVenta
)
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

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    __mapper_args__ = {"version_id_col": version}

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
    ddjj_detalle: Mapped[str | None] = mapped_column(
        EncryptedText,
        nullable=True,
    )
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
    eliminada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    eliminada_por: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    motivo_baja: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    eventos: Mapped[list[VentaEvento]] = relationship(
        back_populates="venta",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="VentaEvento.id",
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


class VentaEvento(Base):
    """Evento inmutable de linaje de una venta."""

    __tablename__ = "venta_eventos"
    __table_args__ = (
        CheckConstraint(
            f"tipo IN ({_TIPOS_EVENTO_SQL})",
            name="ck_venta_eventos_tipo_valido",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venta_id: Mapped[int] = mapped_column(
        ForeignKey("ventas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    estado_anterior: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    estado_nuevo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="operador",
        server_default=text("'operador'"),
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        index=True,
    )

    venta: Mapped[Venta] = relationship(back_populates="eventos")


class Usuario(Base):
    """Usuario local con rol, contraseña y MFA opcional."""

    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(f"rol IN ({_ROLES_SQL})", name="ck_usuarios_rol_valido"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=RolUsuario.OPERADOR.value,
        server_default=text(f"'{RolUsuario.OPERADOR.value}'"),
    )
    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    mfa_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    mfa_last_counter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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

    sesiones: Mapped[list[Sesion]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    codigos_recuperacion: Mapped[list[CodigoRecuperacion]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Sesion(Base):
    """Sesión opaca; solo se guarda el hash del token."""

    __tablename__ = "sesiones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    autenticada: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    mfa_failed_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    ultimo_uso: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    expira_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revocada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    usuario: Mapped[Usuario] = relationship(back_populates="sesiones")


class CodigoRecuperacion(Base):
    """Código de recuperación MFA de un solo uso."""

    __tablename__ = "codigos_recuperacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codigo_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    usado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    usuario: Mapped[Usuario] = relationship(back_populates="codigos_recuperacion")


class SecurityEvent(Base):
    """Evento de seguridad sin PII."""

    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        index=True,
    )


class RetencionPolitica(Base):
    """Plazo de retención por categoría; ``dias=None`` no borra automáticamente."""

    __tablename__ = "retencion_politicas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    categoria: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
        index=True,
    )
    dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )


class LegalHold(Base):
    """Bloqueo de supresión/anonimización para una venta."""

    __tablename__ = "legal_holds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venta_id: Mapped[int] = mapped_column(
        ForeignKey("ventas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    creado_por: Mapped[str] = mapped_column(String(60), nullable=False)
    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    liberado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class SolicitudDerecho(Base):
    """Solicitud de acceso, rectificación, supresión o anonimización."""

    __tablename__ = "solicitudes_derecho"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venta_id: Mapped[int] = mapped_column(
        ForeignKey("ventas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDIENTE",
        server_default=text("'PENDIENTE'"),
        index=True,
    )
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_por: Mapped[str] = mapped_column(String(60), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    resuelto_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ConsentimientoPrivacidad(Base):
    """Constancia del aviso de privacidad aceptado al crear/editar una venta."""

    __tablename__ = "consentimientos_privacidad"
    __table_args__ = (
        UniqueConstraint(
            "venta_id",
            "version",
            name="uq_consentimiento_venta_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venta_id: Mapped[int] = mapped_column(
        ForeignKey("ventas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    aceptado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
