"""Aviso público de privacidad."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ventas_app.config import AVISO_PRIVACIDAD_VERSION

router = APIRouter(tags=["privacidad"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/privacidad", response_class=HTMLResponse, name="privacidad")
def mostrar_privacidad(request: Request) -> HTMLResponse:
    """Muestra el aviso de privacidad versionado, sin requerir sesión."""
    return templates.TemplateResponse(
        request=request,
        name="privacidad.html",
        context={"version": AVISO_PRIVACIDAD_VERSION},
    )


__all__ = ["router"]
