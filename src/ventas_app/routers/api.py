"""Endpoints REST de ventas."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ventas_app.database import get_db
from ventas_app.models import Venta
from ventas_app.schemas import VentaIn, VentaOut
from ventas_app.services.ventas import (
    PlanNoDisponibleError,
    VentaNoEncontradaError,
    crear_venta,
    obtener_venta,
)

router = APIRouter(prefix="/api", tags=["ventas"])

SessionDep = Annotated[Session, Depends(get_db)]


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
