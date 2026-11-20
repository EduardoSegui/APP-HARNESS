"""Exportación del padrón y del lote de cobranzas."""

from __future__ import annotations

import csv
import io
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from ventas_app.models import EstadoVenta, Venta
from ventas_app.services.metricas import construir_filtros

_CABECERAS_PADRON = [
    "ID",
    "Titular",
    "DNI",
    "Email",
    "Teléfono",
    "Plan",
    "Régimen",
    "Medio de pago",
    "Instrumento",
    "CUIL",
    "Adherentes",
    "Subtotal",
    "Descuento %",
    "Aporte",
    "Total",
    "Estado",
    "Fecha de alta",
]

_CABECERAS_COBRANZAS = [
    "ID",
    "Titular",
    "Plan",
    "Medio de pago",
    "Instrumento",
    "Régimen",
    "Subtotal",
    "Descuento %",
    "Descuento monto",
    "Aporte",
    "Total a cobrar",
    "Fecha de alta",
]


def _instrumento(venta: Venta) -> str:
    if venta.pago_ultimos_4:
        return f"{venta.pago_marca_entidad} •••• {venta.pago_ultimos_4}"
    return ""


def _cuil_enmascarado(venta: Venta) -> str:
    if not venta.cuil_titular:
        return ""
    return f"{venta.cuil_titular[:2]}••••••{venta.cuil_titular[-2:]}"


def _descuento_monto(venta: Venta) -> int:
    return (venta.subtotal_base * venta.descuento_porcentaje + 50) // 100


def _ventas_exportacion(
    db: Session,
    *,
    desde: date | None,
    hasta: date | None,
    plan_id: int | None,
    estado: str | None,
) -> list[Venta]:
    estado_exportacion = estado or EstadoVenta.APROBADA.value
    filtros = construir_filtros(
        desde=desde,
        hasta=hasta,
        plan_id=plan_id,
        estado=estado_exportacion,
    )
    return list(
        db.scalars(
            select(Venta)
            .options(
                joinedload(Venta.plan),
                selectinload(Venta.integrantes),
            )
            .where(*filtros)
            .order_by(Venta.creado_en.asc(), Venta.id.asc())
        ).all()
    )


def _filas_padron(ventas: list[Venta]) -> list[list[object]]:
    filas = []
    for venta in ventas:
        adherentes = "; ".join(
            f"{integrante.nombre} {integrante.apellido} ({integrante.dni})"
            for integrante in venta.integrantes
        )
        filas.append(
            [
                venta.id,
                f"{venta.nombre_titular} {venta.apellido_titular}",
                venta.dni_titular,
                venta.email,
                venta.telefono,
                venta.plan.nombre,
                venta.regimen_afiliacion,
                venta.medio_pago,
                _instrumento(venta),
                _cuil_enmascarado(venta),
                adherentes,
                venta.subtotal_base,
                venta.descuento_porcentaje,
                venta.aporte_estimado,
                venta.precio_total,
                venta.estado,
                venta.creado_en.strftime("%Y-%m-%d"),
            ]
        )
    return filas


def _filas_cobranzas(ventas: list[Venta]) -> list[list[object]]:
    return [
        [
            venta.id,
            f"{venta.nombre_titular} {venta.apellido_titular}",
            venta.plan.nombre,
            venta.medio_pago,
            _instrumento(venta),
            venta.regimen_afiliacion,
            venta.subtotal_base,
            venta.descuento_porcentaje,
            _descuento_monto(venta),
            venta.aporte_estimado,
            venta.precio_total,
            venta.creado_en.strftime("%Y-%m-%d"),
        ]
        for venta in ventas
    ]


def _csv(cabeceras: list[str], filas: list[list[object]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(cabeceras)
    writer.writerows(filas)
    return buffer.getvalue()


def generar_exportacion(
    db: Session,
    *,
    tipo: str,
    formato: str,
    desde: date | None = None,
    hasta: date | None = None,
    plan_id: int | None = None,
    estado: str | None = None,
) -> tuple[str, str, str]:
    """Devuelve (contenido, media_type, nombre_archivo)."""
    if tipo not in {"padron", "cobranzas"}:
        raise ValueError("El tipo de exportación no es válido.")
    if formato not in {"csv", "json"}:
        raise ValueError("El formato de exportación no es válido.")

    ventas = _ventas_exportacion(
        db,
        desde=desde,
        hasta=hasta,
        plan_id=plan_id,
        estado=estado,
    )
    cabeceras = (
        _CABECERAS_PADRON if tipo == "padron" else _CABECERAS_COBRANZAS
    )
    filas = (
        _filas_padron(ventas)
        if tipo == "padron"
        else _filas_cobranzas(ventas)
    )
    nombre = f"{tipo}.{formato}"

    if formato == "csv":
        return _csv(cabeceras, filas), "text/csv; charset=utf-8", nombre

    contenido = [
        dict(zip(cabeceras, fila, strict=True))
        for fila in filas
    ]
    return (
        json.dumps(contenido, ensure_ascii=False, indent=2),
        "application/json",
        nombre,
    )


__all__ = ["generar_exportacion"]
