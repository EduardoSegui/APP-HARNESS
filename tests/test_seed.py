"""Tests del seed idempotente de planes y su ejecución al iniciar la app."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ventas_app.database import SessionLocal
from ventas_app.main import app
from ventas_app.models import Plan
from ventas_app.seed import seed_planes

PLANES_ESPERADOS = {
    "Plan Esencial": (45_000, 30_000),
    "Plan Integral": (78_000, 52_000),
    "Plan Superior": (125_000, 85_000),
}


def obtener_planes(db: Session) -> list[Plan]:
    return list(db.scalars(select(Plan).order_by(Plan.id)).all())


def test_seed_crea_los_tres_planes(db: Session) -> None:
    creados = seed_planes(db)

    planes = obtener_planes(db)

    precios = {
        plan.nombre: (plan.precio_titular, plan.precio_adherente)
        for plan in planes
    }

    assert creados == 3
    assert len(planes) == 3
    assert precios == PLANES_ESPERADOS
    assert all(plan.activo for plan in planes)


def test_seed_es_idempotente(db: Session) -> None:
    assert seed_planes(db) == 3

    assert seed_planes(db) == 0
    assert len(obtener_planes(db)) == 3


def test_seed_no_sobrescribe_planes_existentes(db: Session) -> None:
    db.add(
        Plan(
            nombre="Plan Esencial",
            precio_titular=1,
            precio_adherente=1,
        )
    )
    db.commit()

    creados = seed_planes(db)
    planes = obtener_planes(db)
    esencial = next(plan for plan in planes if plan.nombre == "Plan Esencial")

    assert creados == 2
    assert len(planes) == 3
    assert esencial.precio_titular == 1
    assert esencial.precio_adherente == 1


def test_la_app_siembra_los_planes_al_iniciar() -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

    with SessionLocal() as db:
        planes = obtener_planes(db)

    assert len(planes) == 3
    assert {plan.nombre for plan in planes} == set(PLANES_ESPERADOS)
