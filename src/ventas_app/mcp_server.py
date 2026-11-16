"""Servidor MCP local para consultar ventas y actualizar su estado."""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ventas_app.database import SessionLocal
from ventas_app.models import EstadoVenta, Venta
from ventas_app.schemas import VentaOut
from ventas_app.services.estados import (
    ErrorEstadoVenta,
    cambiar_estado_venta,
)
from ventas_app.services.ventas import (
    VentaNoEncontradaError,
    listar_ventas_pendientes as listar_ventas_pendientes_en_db,
    obtener_venta,
)

servidor_mcp = MCPServer(
    "ventas-obra-social",
    version="0.1.0",
    instructions=(
        "Servidor local de ventas de obra social. Permite consultar ventas "
        "pendientes, obtener su detalle y registrar el resultado de la auditoría."
    ),
)


def _serializar_resumen(venta: Venta) -> dict[str, Any]:
    """Convierte una venta en un resumen JSON serializable."""
    return {
        "id": venta.id,
        "titular": f"{venta.nombre_titular} {venta.apellido_titular}",
        "plan": venta.plan.nombre,
        "precio_total": venta.precio_total,
        "creado_en": venta.creado_en.isoformat(),
    }


def _serializar_detalle(venta: Venta) -> dict[str, Any]:
    """Convierte una venta en un detalle JSON serializable."""
    return VentaOut.model_validate(venta).model_dump(mode="json")


@servidor_mcp.tool()
def listar_ventas_pendientes() -> list[dict[str, Any]]:
    """Lista las ventas pendientes de verificación con sus datos principales."""
    db = SessionLocal()
    try:
        return [
            _serializar_resumen(venta)
            for venta in listar_ventas_pendientes_en_db(db)
        ]
    finally:
        db.close()


@servidor_mcp.tool()
def obtener_detalle_venta(venta_id: int) -> dict[str, Any]:
    """Devuelve el detalle completo de una venta por su identificador."""
    db = SessionLocal()
    try:
        try:
            venta = obtener_venta(db, venta_id)
        except VentaNoEncontradaError as exc:
            raise ToolError(str(exc)) from exc

        return _serializar_detalle(venta)
    finally:
        db.close()


@servidor_mcp.tool()
def actualizar_estado_venta(
    venta_id: int,
    estado: Literal["APROBADA", "OBSERVADA"],
    observaciones: str | None = None,
) -> dict[str, Any]:
    """Actualiza el estado de auditoría de una venta pendiente.

    Solo admite las transiciones de PENDIENTE_VERIFICACION a APROBADA u
    OBSERVADA. Al observar, las observaciones son obligatorias.
    """
    try:
        estado_destino = EstadoVenta(estado)
    except ValueError as exc:
        raise ToolError(
            f"Estado inválido: {estado!r}. Debe ser APROBADA u OBSERVADA."
        ) from exc

    if estado_destino not in (EstadoVenta.APROBADA, EstadoVenta.OBSERVADA):
        raise ToolError(
            f"Estado inválido: {estado!r}. Debe ser APROBADA u OBSERVADA."
        )

    db = SessionLocal()
    try:
        try:
            venta = cambiar_estado_venta(
                db,
                venta_id,
                estado_destino,
                observaciones,
            )
        except (VentaNoEncontradaError, ErrorEstadoVenta) as exc:
            raise ToolError(str(exc)) from exc

        return _serializar_detalle(venta)
    finally:
        db.close()


def main() -> None:
    """Ejecuta el servidor MCP por stdio."""
    servidor_mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
