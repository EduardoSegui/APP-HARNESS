"""Seed idempotente de los planes disponibles."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ventas_app.models import Plan

PLANES_SEED: tuple[dict[str, str | int], ...] = (
    {
        "nombre": "Plan Esencial",
        "precio_titular": 45_000,
        "precio_adherente": 30_000,
    },
    {
        "nombre": "Plan Integral",
        "precio_titular": 78_000,
        "precio_adherente": 52_000,
    },
    {
        "nombre": "Plan Superior",
        "precio_titular": 125_000,
        "precio_adherente": 85_000,
    },
)


def seed_planes(db: Session) -> int:
    """Inserta los planes faltantes sin sobreescribir los existentes.

    La comparación se realiza por nombre. Si un plan ya existe, se conservan
    sus precios y su estado actual.

    Returns:
        Cantidad de planes nuevos insertados.
    """
    nombres_existentes = set(db.scalars(select(Plan.nombre)).all())
    planes_nuevos = [
        Plan(**datos)
        for datos in PLANES_SEED
        if datos["nombre"] not in nombres_existentes
    ]

    if not planes_nuevos:
        return 0

    try:
        db.add_all(planes_nuevos)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return len(planes_nuevos)
