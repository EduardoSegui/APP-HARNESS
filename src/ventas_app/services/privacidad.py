"""Privacidad: retención, legal hold, derechos y consentimiento."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ventas_app.config import (
    AVISO_PRIVACIDAD_VERSION,
    RETENCION_COMERCIAL_DIAS,
    RETENCION_SALUD_DIAS,
    RETENCION_SEGURIDAD_DIAS,
)
from ventas_app.models import (
    ConsentimientoPrivacidad,
    EstadoVenta,
    LegalHold,
    RetencionPolitica,
    SecurityEvent,
    SolicitudDerecho,
    TipoEventoVenta,
    Venta,
)
from ventas_app.security import ahora_utc, registrar_evento_seguridad
from ventas_app.services.backup import ErrorBackup, verificar_backup
from ventas_app.services.eventos import registrar_evento
from ventas_app.services.ventas import VentaNoEncontradaError, obtener_venta

CATEGORIA_SEGURIDAD = "SEGURIDAD"
CATEGORIA_COMERCIAL = "COMERCIAL"
CATEGORIA_SALUD = "SALUD"

TIPOS_DERECHO = frozenset(
    {"ACCESO", "RECTIFICACION", "SUPRESION", "ANONIMIZACION"}
)
ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_RESUELTA = "RESUELTA"
ESTADOS_DERECHO = frozenset({ESTADO_PENDIENTE, ESTADO_RESUELTA})


class ErrorPrivacidad(ValueError):
    """Error de negocio en un flujo de privacidad."""


def _dias_opcionales(valor: str) -> int | None:
    if not valor:
        return None
    try:
        dias = int(valor)
    except ValueError as exc:
        raise ErrorPrivacidad(
            "El plazo de retención debe ser un entero o quedar vacío."
        ) from exc
    if dias < 0:
        raise ErrorPrivacidad("El plazo de retención no puede ser negativo.")
    return dias


def asegurar_politicas_default(db: Session) -> list[RetencionPolitica]:
    """Crea las políticas por categoría sin pisar valores existentes."""
    existentes = {
        politica.categoria: politica
        for politica in db.scalars(select(RetencionPolitica)).all()
    }
    valores = {
        CATEGORIA_SEGURIDAD: RETENCION_SEGURIDAD_DIAS,
        CATEGORIA_COMERCIAL: _dias_opcionales(RETENCION_COMERCIAL_DIAS),
        CATEGORIA_SALUD: _dias_opcionales(RETENCION_SALUD_DIAS),
    }
    creadas = []
    for categoria, dias in valores.items():
        if categoria in existentes:
            continue
        politica = RetencionPolitica(
            categoria=categoria,
            dias=dias,
            activo=True,
        )
        db.add(politica)
        creadas.append(politica)
    if creadas:
        db.commit()
    return creadas


def obtener_politica(
    db: Session,
    categoria: str,
) -> RetencionPolitica | None:
    return db.scalar(
        select(RetencionPolitica).where(
            RetencionPolitica.categoria == categoria
        )
    )


def ejecutar_retencion_seguridad(
    db: Session,
    *,
    ahora: datetime | None = None,
) -> int:
    """Borra solo eventos de seguridad vencidos; nunca ventas o salud."""
    asegurar_politicas_default(db)
    politica = obtener_politica(db, CATEGORIA_SEGURIDAD)
    if politica is None or not politica.activo or politica.dias is None:
        return 0
    referencia = ahora or ahora_utc()
    limite = referencia - timedelta(days=politica.dias)
    result = db.execute(
        delete(SecurityEvent).where(SecurityEvent.creado_en < limite)
    )
    eliminados = result.rowcount or 0
    registrar_evento_seguridad(
        db,
        tipo="RETENCION_SEGURIDAD",
        resultado="OK",
        detalle=f"Eventos eliminados: {eliminados}.",
    )
    db.commit()
    return eliminados


def _validar_venta(db: Session, venta_id: int) -> Venta:
    try:
        return obtener_venta(db, venta_id)
    except VentaNoEncontradaError as exc:
        raise ErrorPrivacidad(str(exc)) from exc


def hay_legal_hold(db: Session, venta_id: int) -> bool:
    return (
        db.scalar(
            select(LegalHold.id).where(
                LegalHold.venta_id == venta_id,
                LegalHold.activo.is_(True),
            )
        )
        is not None
    )


def crear_legal_hold(
    db: Session,
    *,
    venta_id: int,
    motivo: str,
    actor: str,
) -> LegalHold:
    _validar_venta(db, venta_id)
    if hay_legal_hold(db, venta_id):
        raise ErrorPrivacidad("La venta ya tiene un legal hold activo.")
    if not motivo.strip():
        raise ErrorPrivacidad("El legal hold requiere un motivo.")
    hold = LegalHold(
        venta_id=venta_id,
        motivo=motivo.strip(),
        creado_por=actor[:60],
        activo=True,
    )
    db.add(hold)
    registrar_evento_seguridad(
        db,
        tipo="LEGAL_HOLD",
        resultado="OK",
        detalle=f"Venta {venta_id}: hold activado.",
    )
    db.commit()
    db.refresh(hold)
    return hold


def liberar_legal_hold(
    db: Session,
    hold_id: int,
    *,
    actor: str,
) -> LegalHold:
    hold = db.get(LegalHold, hold_id)
    if hold is None or not hold.activo:
        raise ErrorPrivacidad("El legal hold no existe o ya está liberado.")
    hold.activo = False
    hold.liberado_en = ahora_utc()
    registrar_evento_seguridad(
        db,
        tipo="LEGAL_HOLD",
        resultado="OK",
        detalle=f"Venta {hold.venta_id}: hold liberado ({actor[:60]}).",
    )
    db.commit()
    db.refresh(hold)
    return hold


def _exigir_backup_y_confirmacion(
    archivo_backup: str | Path | None,
    confirmar: bool,
) -> None:
    if not confirmar:
        raise ErrorPrivacidad(
            "La supresión/anonimización requiere --confirmar del custodio."
        )
    if not archivo_backup:
        raise ErrorPrivacidad(
            "La supresión/anonimización requiere un backup verificable."
        )
    try:
        valido = verificar_backup(archivo_backup)
    except (ValueError, OSError, ErrorBackup) as exc:
        raise ErrorPrivacidad(
            "No se pudo verificar el backup previo."
        ) from exc
    if not valido:
        raise ErrorPrivacidad(
            "El backup previo no pasó checksum/integridad; no se anonimiza."
        )


def _anonymizar_integrantes(venta: Venta) -> None:
    for indice, integrante in enumerate(venta.integrantes, start=1):
        integrante.nombre = "ANONIMIZADO"
        integrante.apellido = "ANONIMIZADO"
        integrante.dni = f"000{indice:05d}"[:8]
        integrante.fecha_nacimiento = date(1900, 1, 1)


def anonimizar_venta(
    db: Session,
    venta_id: int,
    *,
    actor: str,
    archivo_backup: str | Path | None = None,
    confirmar: bool = False,
) -> Venta:
    """Anonimiza PII/salud sin borrar el registro comercial ni su linaje."""
    if hay_legal_hold(db, venta_id):
        raise ErrorPrivacidad(
            "La venta tiene legal hold activo; no se puede anonimizar."
        )
    _exigir_backup_y_confirmacion(archivo_backup, confirmar)
    venta = _validar_venta(db, venta_id)
    venta.nombre_titular = "ANONIMIZADO"
    venta.apellido_titular = "ANONIMIZADO"
    venta.dni_titular = "00000000"
    venta.fecha_nacimiento_titular = date(1900, 1, 1)
    venta.email = "anonimizado@invalid.local"
    venta.telefono = "000000"
    venta.calle = "ANONIMIZADO"
    venta.altura = "0"
    venta.piso_depto = None
    venta.localidad = "ANONIMIZADA"
    venta.provincia = "ANONIMIZADA"
    venta.codigo_postal = "0000"
    venta.pago_titular = None
    venta.pago_marca_entidad = None
    venta.pago_ultimos_4 = None
    venta.pago_vencimiento = None
    venta.pago_cuil = None
    venta.ddjj_completada = False
    venta.ddjj_preexistencias = False
    venta.ddjj_internaciones = False
    venta.ddjj_embarazo = False
    venta.ddjj_medicacion_cronica = False
    venta.ddjj_discapacidad = False
    venta.ddjj_detalle = None
    venta.cuil_titular = None
    venta.aporte_estimado = 0
    venta.observaciones = None
    _anonymizar_integrantes(venta)
    registrar_evento(
        db,
        venta,
        TipoEventoVenta.EDITADA,
        detalle="Anonimización por solicitud de derechos.",
        actor=actor[:30],
        estado_anterior=venta.estado,
        estado_nuevo=venta.estado,
    )
    db.commit()
    db.refresh(venta)
    return venta


def crear_solicitud_derecho(
    db: Session,
    *,
    venta_id: int,
    tipo: str,
    detalle: str | None,
    actor: str,
) -> SolicitudDerecho:
    tipo_normalizado = tipo.strip().upper()
    if tipo_normalizado not in TIPOS_DERECHO:
        raise ErrorPrivacidad("Tipo de derecho no válido.")
    _validar_venta(db, venta_id)
    solicitud = SolicitudDerecho(
        venta_id=venta_id,
        tipo=tipo_normalizado,
        detalle=detalle,
        creado_por=actor[:60],
        estado=ESTADO_PENDIENTE,
    )
    db.add(solicitud)
    registrar_evento_seguridad(
        db,
        tipo="DSR",
        resultado="PENDIENTE",
        detalle=f"Solicitud {tipo_normalizado} para venta {venta_id}.",
    )
    db.commit()
    db.refresh(solicitud)
    return solicitud


def resolver_solicitud_derecho(
    db: Session,
    solicitud_id: int,
    *,
    actor: str,
    archivo_backup: str | Path | None = None,
    confirmar: bool = False,
) -> SolicitudDerecho:
    solicitud = db.get(SolicitudDerecho, solicitud_id)
    if solicitud is None:
        raise ErrorPrivacidad("La solicitud no existe.")
    if solicitud.estado == ESTADO_RESUELTA:
        raise ErrorPrivacidad("La solicitud ya fue resuelta.")
    if solicitud.tipo in {"SUPRESION", "ANONIMIZACION"}:
        if hay_legal_hold(db, solicitud.venta_id):
            raise ErrorPrivacidad(
                "La venta tiene legal hold activo; no se puede suprimir ni "
                "anonimizar."
            )
        _exigir_backup_y_confirmacion(archivo_backup, confirmar)
        anonimizar_venta(
            db,
            solicitud.venta_id,
            actor=actor,
            archivo_backup=archivo_backup,
            confirmar=confirmar,
        )
    solicitud.estado = ESTADO_RESUELTA
    solicitud.resuelto_en = ahora_utc()
    registrar_evento_seguridad(
        db,
        tipo="DSR",
        resultado="RESUELTA",
        detalle=f"Solicitud {solicitud.tipo} para venta {solicitud.venta_id}.",
    )
    db.commit()
    db.refresh(solicitud)
    return solicitud


def registrar_consentimiento(
    db: Session,
    *,
    venta_id: int,
    version: str | None = None,
) -> ConsentimientoPrivacidad:
    version_final = (version or AVISO_PRIVACIDAD_VERSION)[:30]
    existente = db.scalar(
        select(ConsentimientoPrivacidad).where(
            ConsentimientoPrivacidad.venta_id == venta_id,
            ConsentimientoPrivacidad.version == version_final,
        )
    )
    if existente is not None:
        return existente
    consentimiento = ConsentimientoPrivacidad(
        venta_id=venta_id,
        version=version_final,
    )
    db.add(consentimiento)
    return consentimiento


def listar_solicitudes(db: Session) -> list[SolicitudDerecho]:
    return list(
        db.scalars(
            select(SolicitudDerecho).order_by(SolicitudDerecho.id.desc())
        ).all()
    )


def hay_datos_comerciales_o_salud(db: Session) -> bool:
    """Indica si hay ventas; la retención automática nunca las borra."""
    return db.scalar(select(Venta.id).limit(1)) is not None


__all__ = [
    "CATEGORIA_COMERCIAL",
    "CATEGORIA_SALUD",
    "CATEGORIA_SEGURIDAD",
    "ESTADO_PENDIENTE",
    "ESTADO_RESUELTA",
    "ErrorPrivacidad",
    "TIPOS_DERECHO",
    "anonimizar_venta",
    "asegurar_politicas_default",
    "crear_legal_hold",
    "crear_solicitud_derecho",
    "ejecutar_retencion_seguridad",
    "hay_datos_comerciales_o_salud",
    "hay_legal_hold",
    "liberar_legal_hold",
    "listar_solicitudes",
    "obtener_politica",
    "registrar_consentimiento",
    "resolver_solicitud_derecho",
]
