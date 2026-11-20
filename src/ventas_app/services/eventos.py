"""Registro y consulta del linaje de las ventas."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ventas_app.models import TipoEventoVenta, Venta, VentaEvento


def _normalizar_tipo(tipo: TipoEventoVenta | str) -> TipoEventoVenta:
    try:
        return TipoEventoVenta(tipo)
    except ValueError as exc:
        raise ValueError(f"Tipo de evento no reconocido: {tipo}") from exc


def registrar_evento(
    db: Session,
    venta: Venta,
    tipo: TipoEventoVenta | str,
    *,
    detalle: str | None = None,
    actor: str = "operador",
    estado_anterior: str | None = None,
    estado_nuevo: str | None = None,
) -> VentaEvento:
    """Agrega un evento a la transacción actual, sin hacer commit."""
    evento = VentaEvento(
        venta_id=venta.id,
        tipo=_normalizar_tipo(tipo).value,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        detalle=detalle,
        actor=actor,
    )
    db.add(evento)
    return evento


def listar_eventos(db: Session, venta_id: int) -> list[VentaEvento]:
    """Devuelve los eventos de una venta, del más reciente al más antiguo."""
    return list(
        db.scalars(
            select(VentaEvento)
            .where(VentaEvento.venta_id == venta_id)
            .order_by(
                VentaEvento.creado_en.desc(),
                VentaEvento.id.desc(),
            )
        ).all()
    )


__all__ = ["listar_eventos", "registrar_evento"]
