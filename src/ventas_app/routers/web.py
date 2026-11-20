"""Rutas HTML y configuración de templates del wizard."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ventas_app.database import get_db
from ventas_app.models import EstadoVenta, Parentesco, Plan, Venta
from ventas_app.schemas import VentaOut
from ventas_app.services.ventas import (
    VentaNoEncontradaError,
    listar_ventas,
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


@router.get("/ventas", response_class=HTMLResponse, name="panel_ventas")
def mostrar_panel_ventas(request: Request, db: SessionDep) -> HTMLResponse:
    """Renderiza el panel de ventas registradas."""
    return templates.TemplateResponse(
        request=request,
        name="panel.html",
        context={"ventas": listar_ventas(db)},
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
            "descuento_monto": descuento_monto,
            "base_bonificada": venta.subtotal_base - descuento_monto,
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
