"""Servicios de transición de estado de ventas."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ventas_app.models import EstadoVenta, TipoEventoVenta, Venta
from ventas_app.services.eventos import registrar_evento
from ventas_app.services.ventas import obtener_venta


class ErrorEstadoVenta(ValueError):
    """Error de negocio al intentar cambiar el estado de una venta."""


class TransicionEstadoInvalidaError(ErrorEstadoVenta):
    """La transición solicitada no está permitida."""


class ObservacionesRequeridasError(ErrorEstadoVenta):
    """Una venta observada requiere al menos una observación."""


def _convertir_estado(valor: EstadoVenta | str, descripcion: str) -> EstadoVenta:
    try:
        return EstadoVenta(valor)
    except ValueError as exc:
        raise TransicionEstadoInvalidaError(
            f"El {descripcion} '{valor}' no es un estado válido."
        ) from exc


def preparar_transicion(
    venta: Venta,
    nuevo_estado: EstadoVenta | str,
    observaciones: str | None = None,
) -> tuple[EstadoVenta, str | None]:
    """Valida una transición y devuelve el estado y las observaciones finales.

    Solo se permite avanzar desde ``PENDIENTE_VERIFICACION`` hacia
    ``APROBADA`` u ``OBSERVADA``. Aprobar siempre deja las observaciones en
    ``None``; observar exige un texto no vacío.
    """
    estado_actual = _convertir_estado(venta.estado, "estado actual de la venta")
    estado_destino = _convertir_estado(nuevo_estado, "estado destino")

    if estado_actual is not EstadoVenta.PENDIENTE_VERIFICACION:
        raise TransicionEstadoInvalidaError(
            f"La venta {venta.id} está en estado {estado_actual.value} "
            "y no admite nuevas transiciones."
        )

    if estado_destino not in (EstadoVenta.APROBADA, EstadoVenta.OBSERVADA):
        raise TransicionEstadoInvalidaError(
            "El estado destino debe ser APROBADA u OBSERVADA."
        )

    if estado_destino is EstadoVenta.APROBADA:
        return estado_destino, None

    observaciones_normalizadas = (
        observaciones.strip() if observaciones is not None else None
    )
    if not observaciones_normalizadas:
        raise ObservacionesRequeridasError(
            "La transición a OBSERVADA requiere al menos una observación."
        )

    return estado_destino, observaciones_normalizadas


def cambiar_estado_venta(
    db: Session,
    venta_id: int,
    nuevo_estado: EstadoVenta | str,
    observaciones: str | None = None,
    *,
    actor: str = "auditor",
) -> Venta:
    """Aplica y persiste una transición de estado de forma atómica.

    Raises:
        VentaNoEncontradaError: Si la venta no existe.
        TransicionEstadoInvalidaError: Si la transición no está permitida.
        ObservacionesRequeridasError: Si se intenta observar sin observaciones.
    """
    venta = obtener_venta(db, venta_id)
    estado_final, observaciones_finales = preparar_transicion(
        venta,
        nuevo_estado,
        observaciones,
    )

    estado_anterior = venta.estado
    venta.estado = estado_final.value
    venta.observaciones = observaciones_finales

    try:
        tipo = (
            TipoEventoVenta.AUDITADA_APROBADA
            if estado_final is EstadoVenta.APROBADA
            else TipoEventoVenta.AUDITADA_OBSERVADA
        )
        detalle = (
            "Aprobada por auditoría."
            if estado_final is EstadoVenta.APROBADA
            else (observaciones_finales or "Observada por auditoría.")
        )
        registrar_evento(
            db,
            venta,
            tipo,
            detalle=detalle,
            actor=actor,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_final.value,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(venta)
    return venta


__all__ = [
    "ErrorEstadoVenta",
    "ObservacionesRequeridasError",
    "TransicionEstadoInvalidaError",
    "cambiar_estado_venta",
    "preparar_transicion",
]
