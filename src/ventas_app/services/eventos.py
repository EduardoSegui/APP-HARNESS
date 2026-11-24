"""Registro y consulta del linaje de las ventas."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ventas_app.models import TipoEventoVenta, Venta, VentaEvento
from ventas_app.redaction import redactar_pii


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
        detalle=redactar_pii(detalle),
        actor=actor[:30],
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


def redactar_eventos_venta(venta_id: int) -> int:
    """Redacta PII histórica de eventos bajo una operación DSR controlada.

    Es la única excepción deliberada a los triggers append-only: se ejecuta
    después de un backup verificado y confirmación del custodio, y vuelve a
    activar los triggers al terminar.
    """
    from ventas_app.database import (
        activar_triggers_eventos,
        desactivar_triggers_eventos,
        engine,
    )

    desactivar_triggers_eventos()
    try:
        with engine.begin() as conexion:
            filas = conexion.exec_driver_sql(
                "SELECT id, detalle FROM venta_eventos WHERE venta_id = ?",
                (venta_id,),
            ).fetchall()
            cambiados = 0
            for evento_id, detalle in filas:
                redactado = redactar_pii(detalle)
                if redactado != detalle:
                    conexion.exec_driver_sql(
                        "UPDATE venta_eventos SET detalle = ? WHERE id = ?",
                        (redactado, evento_id),
                    )
                    cambiados += 1
        return cambiados
    finally:
        activar_triggers_eventos()


__all__ = ["listar_eventos", "redactar_eventos_venta", "registrar_evento"]
