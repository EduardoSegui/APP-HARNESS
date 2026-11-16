"""Rutas HTML y configuración de templates del wizard."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ventas_app.database import get_db
from ventas_app.models import Parentesco, Plan

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
        },
    )
