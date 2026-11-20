"""Endpoints REST de ventas y auditoría."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ventas_app.auditor import ejecutar_auditoria
from ventas_app.database import get_db
from ventas_app.models import Venta
from ventas_app.schemas import AuditoriaOut, VentaIn, VentaOut, VentaUpdateIn
from ventas_app.services.ventas import (
    DatosPagoInvalidosError,
    PlanNoDisponibleError,
    VentaNoEditableError,
    VentaNoEncontradaError,
    actualizar_venta,
    crear_venta,
    obtener_venta,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ventas"])

SessionDep = Annotated[Session, Depends(get_db)]


@router.post(
    "/auditar",
    response_model=AuditoriaOut,
    tags=["auditor"],
)
def auditar_endpoint() -> dict[str, Any]:
    """Ejecuta el Agente Auditor sobre las ventas pendientes."""
    try:
        return ejecutar_auditoria()
    except Exception as exc:
        logger.exception("Falló la ejecución del Agente Auditor")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo ejecutar la auditoría.",
        ) from exc


@router.post(
    "/ventas",
    response_model=VentaOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_venta_endpoint(payload: VentaIn, db: SessionDep) -> Venta:
    """Crea una venta completa y devuelve el comprobante persistido."""
    try:
        return crear_venta(db, payload)
    except PlanNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/ventas/{venta_id}", response_model=VentaOut)
def obtener_venta_endpoint(venta_id: int, db: SessionDep) -> Venta:
    """Devuelve el detalle de una venta existente."""
    try:
        return obtener_venta(db, venta_id)
    except VentaNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.put("/ventas/{venta_id}", response_model=VentaOut)
def actualizar_venta_endpoint(
    venta_id: int,
    payload: VentaUpdateIn,
    db: SessionDep,
) -> Venta:
    """Edita un legajo pendiente u observado y lo devuelve a auditoría."""
    try:
        return actualizar_venta(db, venta_id, payload)
    except VentaNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except VentaNoEditableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PlanNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except DatosPagoInvalidosError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
