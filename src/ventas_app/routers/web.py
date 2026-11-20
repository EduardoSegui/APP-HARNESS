"""Rutas HTML y configuración de templates del wizard."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ventas_app.database import get_db
from ventas_app.models import (
    EstadoVenta,
    MedioPago,
    Parentesco,
    Plan,
    RegimenAfiliacion,
    Venta,
)
from ventas_app.schemas import VentaOut
from ventas_app.services.eventos import listar_eventos
from ventas_app.services.ventas import (
    VentaNoEncontradaError,
    buscar_ventas,
    obtener_venta,
)

PACKAGE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"

PROVINCIAS: tuple[str, ...] = (
    "Ciudad Autónoma de Buenos Aires",
    "Buenos Aires",
    "Catamarca",
    "Chaco",
    "Chubut",
    "Córdoba",
    "Corrientes",
    "Entre Ríos",
    "Formosa",
    "Jujuy",
    "La Pampa",
    "La Rioja",
    "Mendoza",
    "Misiones",
    "Neuquén",
    "Río Negro",
    "Salta",
    "San Juan",
    "San Luis",
    "Santa Cruz",
    "Santa Fe",
    "Santiago del Estero",
    "Tierra del Fuego, Antártida e Islas del Atlántico Sur",
    "Tucumán",
)

SessionDep = Annotated[Session, Depends(get_db)]

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _formato_pesos(valor: int) -> str:
    return f"${valor:,.0f}".replace(",", ".")


templates.env.filters["pesos"] = _formato_pesos

router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse, name="wizard")
def mostrar_wizard(request: Request, db: SessionDep) -> HTMLResponse:
    """Renderiza el wizard de carga de ventas en tres etapas."""
    planes = list(
        db.scalars(
            select(Plan).where(Plan.activo.is_(True)).order_by(Plan.id)
        ).all()
    )

    return templates.TemplateResponse(
        request=request,
        name="wizard.html",
        context={
            "planes": planes,
            "parentescos": [parentesco.value for parentesco in Parentesco],
            "provincias": PROVINCIAS,
            "modo_edicion": False,
        },
    )


def _url_panel(filtros: dict[str, object], pagina: int) -> str:
    parametros = {
        clave: valor
        for clave, valor in filtros.items()
        if valor not in (None, "")
    }
    parametros["pagina"] = pagina
    return "/ventas?" + urlencode(parametros)


@router.get("/ventas", response_class=HTMLResponse, name="panel_ventas")
def mostrar_panel_ventas(
    request: Request,
    db: SessionDep,
    q: str | None = None,
    estado: str | None = None,
    plan_id: str | None = None,
    medio_pago: str | None = None,
    regimen_afiliacion: str | None = None,
    pagina: int = Query(default=1, ge=1),
) -> HTMLResponse:
    """Renderiza el panel con búsqueda, filtros y paginación."""
    plan_id_valor: int | None = None
    if plan_id:
        try:
            plan_id_valor = int(plan_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="El plan de filtro no es válido.",
            ) from exc

    filtros = {
        "q": q,
        "estado": estado,
        "plan_id": plan_id_valor,
        "medio_pago": medio_pago,
        "regimen_afiliacion": regimen_afiliacion,
    }
    try:
        ventas, total = buscar_ventas(
            db,
            q=q,
            estado=estado,
            plan_id=plan_id_valor,
            medio_pago=medio_pago,
            regimen_afiliacion=regimen_afiliacion,
            pagina=pagina,
            por_pagina=20,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    total_paginas = max(1, (total + 19) // 20)
    planes = list(db.scalars(select(Plan).order_by(Plan.id)).all())
    hay_filtros = any(valor not in (None, "") for valor in filtros.values())

    return templates.TemplateResponse(
        request=request,
        name="panel.html",
        context={
            "ventas": ventas,
            "total_ventas": total,
            "pagina": pagina,
            "total_paginas": total_paginas,
            "hay_filtros": hay_filtros,
            "filtros": filtros,
            "planes": planes,
            "medios_pago": [medio.value for medio in MedioPago],
            "regimenes": [regimen.value for regimen in RegimenAfiliacion],
            "url_pagina_anterior": (
                _url_panel(filtros, pagina - 1) if pagina > 1 else None
            ),
            "url_pagina_siguiente": (
                _url_panel(filtros, pagina + 1)
                if pagina < total_paginas
                else None
            ),
        },
    )


def _obtener_venta_o_404(db: Session, venta_id: int) -> Venta:
    try:
        return obtener_venta(db, venta_id)
    except VentaNoEncontradaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/ventas/{venta_id}", response_class=HTMLResponse, name="detalle_venta")
def mostrar_detalle_venta(
    request: Request,
    venta_id: int,
    db: SessionDep,
) -> HTMLResponse:
    """Renderiza una ficha de legajo en modo lectura."""
    venta = _obtener_venta_o_404(db, venta_id)
    descuento_monto = (
        venta.subtotal_base * venta.descuento_porcentaje + 50
    ) // 100
    return templates.TemplateResponse(
        request=request,
        name="legajo.html",
        context={
            "venta": venta,
            "eventos": listar_eventos(db, venta_id),
            "descuento_monto": descuento_monto,
            "base_bonificada": venta.subtotal_base - descuento_monto,
        },
    )


@router.get(
    "/ventas/{venta_id}/credencial",
    response_class=HTMLResponse,
    name="credencial_venta",
)
def mostrar_credencial(
    request: Request,
    venta_id: int,
    db: SessionDep,
) -> HTMLResponse:
    """Emite una credencial provisoria solo para ventas aprobadas."""
    venta = _obtener_venta_o_404(db, venta_id)
    if venta.estado != EstadoVenta.APROBADA.value:
        raise HTTPException(
            status_code=404,
            detail="La credencial solo está disponible para ventas aprobadas.",
        )
    return templates.TemplateResponse(
        request=request,
        name="credencial.html",
        context={
            "venta": venta,
            "numero_afiliado": f"OS-{venta.id:06d}",
            "fecha_emision": venta.actualizado_en,
        },
    )


@router.get(
    "/ventas/{venta_id}/editar",
    response_class=HTMLResponse,
    name="editar_venta",
    response_model=None,
)
def mostrar_edicion_venta(
    request: Request,
    venta_id: int,
    db: SessionDep,
) -> HTMLResponse | RedirectResponse:
    """Renderiza el wizard precargado para ventas pendientes u observadas."""
    venta = _obtener_venta_o_404(db, venta_id)
    if venta.estado == EstadoVenta.APROBADA.value:
        return RedirectResponse(url=f"/ventas/{venta_id}", status_code=303)

    planes = list(
        db.scalars(
            select(Plan).where(Plan.activo.is_(True)).order_by(Plan.id)
        ).all()
    )
    venta_data = VentaOut.model_validate(venta).model_dump(mode="json")
    return templates.TemplateResponse(
        request=request,
        name="wizard.html",
        context={
            "planes": planes,
            "parentescos": [parentesco.value for parentesco in Parentesco],
            "provincias": PROVINCIAS,
            "modo_edicion": True,
            "venta_data": venta_data,
        },
    )
