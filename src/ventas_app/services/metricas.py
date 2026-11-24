"""Métricas agregadas del negocio para el tablero ejecutivo."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from sqlalchemy import Integer, func, or_, select
from sqlalchemy.orm import Session

from ventas_app.models import (
    EstadoVenta,
    Integrante,
    MedioPago,
    Plan,
    RegimenAfiliacion,
    Venta,
)

_ETIQUETAS_MEDIO = {
    MedioPago.TARJETA_CREDITO.value: "Tarjeta de crédito",
    MedioPago.CBU.value: "CBU / Débito automático",
    MedioPago.PAGO_FACIL.value: "Pago Fácil / Oficinas",
    MedioPago.COBRADOR_DOMICILIO.value: "Cobrador a domicilio",
}
_ETIQUETAS_REGIMEN = {
    RegimenAfiliacion.PARTICULAR.value: "Particular",
    RegimenAfiliacion.RELACION_DEPENDENCIA.value: "Relación de dependencia",
    RegimenAfiliacion.MONOTRIBUTO.value: "Monotributo",
}
_ETIQUETAS_MOTIVO = {
    "R1": "Edad del titular",
    "R2": "DNI duplicado",
    "R3": "Datos obligatorios",
    "R4": "Código postal",
    "R5": "Plan, pago y precio",
    "R6": "Integridad del legajo",
    "R7": "DDJJ / revisión médica",
    "R8": "Régimen y aportes",
}


def construir_filtros(
    *,
    q: str | None = None,
    estado: str | None = None,
    plan_id: int | None = None,
    medio_pago: str | None = None,
    regimen_afiliacion: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> list:
    """Construye filtros SQL comunes para métricas y exportaciones."""
    if desde is not None and hasta is not None and desde > hasta:
        raise ValueError("La fecha 'desde' no puede ser posterior a 'hasta'.")

    filtros = [Venta.eliminada_en.is_(None)]
    texto = (q or "").strip()
    if texto:
        patron = f"%{texto}%"
        filtros.append(
            or_(
                Venta.dni_titular.ilike(patron),
                Venta.nombre_titular.ilike(patron),
                Venta.apellido_titular.ilike(patron),
            )
        )
    if estado:
        try:
            filtros.append(Venta.estado == EstadoVenta(estado).value)
        except ValueError as exc:
            raise ValueError("El estado de filtro no es válido.") from exc
    if plan_id is not None:
        if plan_id <= 0:
            raise ValueError("El plan de filtro no es válido.")
        filtros.append(Venta.plan_id == plan_id)
    if medio_pago:
        try:
            filtros.append(Venta.medio_pago == MedioPago(medio_pago).value)
        except ValueError as exc:
            raise ValueError("El medio de pago de filtro no es válido.") from exc
    if regimen_afiliacion:
        try:
            filtros.append(
                Venta.regimen_afiliacion
                == RegimenAfiliacion(regimen_afiliacion).value
            )
        except ValueError as exc:
            raise ValueError("El régimen de filtro no es válido.") from exc
    if desde is not None:
        filtros.append(func.date(Venta.creado_en) >= desde)
    if hasta is not None:
        filtros.append(func.date(Venta.creado_en) <= hasta)
    return filtros


def _distribucion(
    db: Session,
    columna,
    filtros: list,
    *,
    etiquetas: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    filas = db.execute(
        select(
            columna,
            func.count(Venta.id),
            func.coalesce(func.sum(Venta.precio_total), 0),
        )
        .where(*filtros)
        .group_by(columna)
        .order_by(columna)
    ).all()
    total_dimension = sum(int(cantidad) for _, cantidad, _ in filas)
    return [
        {
            "etiqueta": (etiquetas or {}).get(str(valor), str(valor)),
            "cantidad": int(cantidad),
            "total": int(total),
            "porcentaje": (
                round(int(cantidad) / total_dimension * 100, 1)
                if total_dimension
                else 0.0
            ),
        }
        for valor, cantidad, total in filas
    ]


def _motivos_observacion(db: Session, filtros: list) -> list[dict[str, object]]:
    observaciones = db.scalars(
        select(Venta.observaciones).where(
            *filtros,
            Venta.estado == EstadoVenta.OBSERVADA.value,
            Venta.observaciones.is_not(None),
        )
    ).all()
    conteo: Counter[str] = Counter()
    for texto in observaciones:
        for coincidencia in re.finditer(r"^(R\d+):", texto or "", re.MULTILINE):
            conteo[coincidencia.group(1)] += 1
    total = sum(conteo.values())
    return [
        {
            "codigo": f"R{indice}",
            "etiqueta": _ETIQUETAS_MOTIVO[f"R{indice}"],
            "cantidad": conteo.get(f"R{indice}", 0),
            "porcentaje": (
                round(conteo.get(f"R{indice}", 0) / total * 100, 1)
                if total
                else 0.0
            ),
        }
        for indice in range(1, 9)
    ]


def calcular_metricas(
    db: Session,
    *,
    desde: date | None = None,
    hasta: date | None = None,
    plan_id: int | None = None,
    estado: str | None = None,
) -> dict[str, object]:
    """Calcula el tablero ejecutivo con una foto del padrón."""
    filtros = construir_filtros(
        desde=desde,
        hasta=hasta,
        plan_id=plan_id,
        estado=estado,
    )
    estados = dict(
        db.execute(
            select(Venta.estado, func.count(Venta.id))
            .where(*filtros)
            .group_by(Venta.estado)
        ).all()
    )
    total = sum(int(cantidad) for cantidad in estados.values())
    pendientes = int(estados.get(EstadoVenta.PENDIENTE_VERIFICACION.value, 0))
    aprobadas = int(estados.get(EstadoVenta.APROBADA.value, 0))
    observadas = int(estados.get(EstadoVenta.OBSERVADA.value, 0))

    filtros_aprobadas = [
        *filtros,
        Venta.estado == EstadoVenta.APROBADA.value,
    ]
    adherentes = int(
        db.scalar(
            select(func.count(Integrante.id))
            .join(Venta, Integrante.venta_id == Venta.id)
            .where(*filtros_aprobadas)
        )
        or 0
    )
    mrr_bruto, aportes, neto = db.execute(
        select(
            func.coalesce(func.sum(Venta.subtotal_base), 0),
            func.coalesce(func.sum(Venta.aporte_estimado), 0),
            func.coalesce(func.sum(Venta.precio_total), 0),
        ).where(*filtros_aprobadas)
    ).one()
    # El cast a entero hace el redondeo half-up por venta antes de sumar.
    # Sin él, SQLite suma valores flotantes (por ejemplo 39000.5 + 9000.5).
    descuento_expr = func.cast(
        (Venta.subtotal_base * Venta.descuento_porcentaje + 50) / 100,
        Integer,
    )
    descuentos = int(
        db.scalar(
            select(func.coalesce(func.sum(descuento_expr), 0)).where(
                *filtros_aprobadas
            )
        )
        or 0
    )
    mrr_bruto = int(mrr_bruto)
    aportes = int(aportes)
    neto = int(neto)
    personas = aprobadas + adherentes

    planes = db.execute(
        select(
            Plan.nombre,
            func.count(Venta.id),
            func.coalesce(func.sum(Venta.precio_total), 0),
        )
        .join(Venta, Venta.plan_id == Plan.id)
        .where(*filtros_aprobadas)
        .group_by(Plan.id, Plan.nombre)
        .order_by(Plan.nombre)
    ).all()

    planes_total = sum(int(cantidad) for _, cantidad, _ in planes)
    return {
        "desde": desde,
        "hasta": hasta,
        "plan_id": plan_id,
        "estado": estado,
        "total_ventas": total,
        "pendientes": pendientes,
        "aprobadas": aprobadas,
        "observadas": observadas,
        "tasa_aprobacion": round(aprobadas / total * 100, 2) if total else 0.0,
        "tasa_observacion": round(observadas / total * 100, 2) if total else 0.0,
        "titulares_cubiertos": aprobadas,
        "adherentes_cubiertos": adherentes,
        "personas_cubiertas": personas,
        "mrr_bruto": mrr_bruto,
        "descuentos": descuentos,
        "aportes": aportes,
        "recaudacion_neta": neto,
        "ticket_promedio": round(neto / aprobadas, 2) if aprobadas else 0.0,
        "ticket_promedio_persona": round(neto / personas, 2) if personas else 0.0,
        "por_plan": [
            {
                "etiqueta": str(nombre),
                "cantidad": int(cantidad),
                "total": int(total_plan),
                "porcentaje": (
                    round(int(cantidad) / planes_total * 100, 1)
                    if planes_total
                    else 0.0
                ),
            }
            for nombre, cantidad, total_plan in planes
        ],
        "por_medio_pago": _distribucion(
            db,
            Venta.medio_pago,
            filtros_aprobadas,
            etiquetas=_ETIQUETAS_MEDIO,
        ),
        "por_regimen": _distribucion(
            db,
            Venta.regimen_afiliacion,
            filtros_aprobadas,
            etiquetas=_ETIQUETAS_REGIMEN,
        ),
        "motivos_observacion": _motivos_observacion(db, filtros),
    }


__all__ = ["calcular_metricas", "construir_filtros"]
