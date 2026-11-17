#!/usr/bin/env python3
"""Carga ventas de demostración pendientes de auditoría en ``ventas.db``.

Las ventas quedan en estado ``PENDIENTE_VERIFICACION`` para poder probar el
botón de auditoría en vivo del panel. El script es idempotente por email: si una
venta demo ya existe, no se duplica.

Uso:
    uv run python scripts/cargar_demo.py
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from ventas_app.database import SessionLocal, init_db
from ventas_app.models import EstadoVenta, Plan, Venta
from ventas_app.schemas import VentaIn
from ventas_app.seed import seed_planes
from ventas_app.services.ventas import crear_venta

DEMO_EMAILS = (
    "demo.f08.1@example.com",
    "demo.f08.2@example.com",
    "demo.f08.3@example.com",
    "demo.f08.4@example.com",
)

# La venta 4 se crea con DNIs únicos porque ``VentaIn`` los valida. Luego se
# cambia el DNI del titular por el del adherente para simular el dato inválido
# que debe detectar la regla R2 del auditor.
_DNI_DUPLICADO = "27123457"


def _plan_id(db, nombre: str) -> int:
    plan = db.scalar(select(Plan).where(Plan.nombre == nombre))
    if plan is None:
        raise RuntimeError(f"No existe el plan '{nombre}'.")
    return plan.id


def _ventas_demo(db) -> list[VentaIn]:
    return [
        VentaIn(
            nombre_titular="Lucía",
            apellido_titular="Fernández",
            dni_titular="28456789",
            fecha_nacimiento_titular=date(1984, 4, 12),
            email=DEMO_EMAILS[0],
            telefono="+54 11 4555-1001",
            calle="Av. Santa Fe",
            altura="2500",
            piso_depto="4 B",
            localidad="Ciudad Autónoma de Buenos Aires",
            provincia="Ciudad Autónoma de Buenos Aires",
            codigo_postal="1425",
            plan_id=_plan_id(db, "Plan Integral"),
            integrantes=[
                {
                    "nombre": "Martín",
                    "apellido": "Fernández",
                    "dni": "29456780",
                    "fecha_nacimiento": date(1983, 8, 20),
                    "parentesco": "Cónyuge/Pareja",
                },
                {
                    "nombre": "Sofía",
                    "apellido": "Fernández",
                    "dni": "42123456",
                    "fecha_nacimiento": date(2010, 6, 15),
                    "parentesco": "Hijo/a",
                },
            ],
        ),
        VentaIn(
            nombre_titular="Carlos",
            apellido_titular="Gómez",
            dni_titular="25123456",
            fecha_nacimiento_titular=date(1975, 11, 3),
            email=DEMO_EMAILS[1],
            telefono="+54 351 455-2002",
            calle="Av. Colón",
            altura="850",
            piso_depto=None,
            localidad="Córdoba",
            provincia="Córdoba",
            codigo_postal="5000",
            plan_id=_plan_id(db, "Plan Esencial"),
            integrantes=[],
        ),
        VentaIn(
            nombre_titular="Mateo",
            apellido_titular="López",
            dni_titular="50123456",
            fecha_nacimiento_titular=date(2012, 9, 18),
            email=DEMO_EMAILS[2],
            telefono="+54 221 455-3003",
            calle="Calle 50",
            altura="1200",
            piso_depto=None,
            localidad="La Plata",
            provincia="Buenos Aires",
            codigo_postal="1900",
            plan_id=_plan_id(db, "Plan Superior"),
            integrantes=[],
        ),
        VentaIn(
            nombre_titular="Valentina",
            apellido_titular="Ruiz",
            dni_titular="27123456",
            fecha_nacimiento_titular=date(1988, 2, 25),
            email=DEMO_EMAILS[3],
            telefono="+54 341 455-4004",
            calle="Calle San Luis",
            altura="1450",
            piso_depto=None,
            localidad="Rosario",
            provincia="Santa Fe",
            codigo_postal="2000",
            plan_id=_plan_id(db, "Plan Integral"),
            integrantes=[
                {
                    "nombre": "Julián",
                    "apellido": "Ruiz",
                    "dni": _DNI_DUPLICADO,
                    "fecha_nacimiento": date(2012, 1, 10),
                    "parentesco": "Hijo/a",
                }
            ],
        ),
    ]


def cargar_demo() -> int:
    """Inserta las cuatro ventas demo y devuelve el total encontrado."""
    init_db()

    with SessionLocal() as db:
        seed_planes(db)
        existentes = set(
            db.scalars(
                select(Venta.email).where(Venta.email.in_(DEMO_EMAILS))
            ).all()
        )

        for datos in _ventas_demo(db):
            if datos.email in existentes:
                print(f"= Venta demo ya existente: {datos.email}")
                continue

            venta = crear_venta(db, datos)

            if datos.email == DEMO_EMAILS[3]:
                # Simula un dato inválido que no pudo entrar por la API:
                # el titular termina con el mismo DNI que su adherente.
                venta.dni_titular = _DNI_DUPLICADO
                db.commit()

            print(
                f"+ Venta #{venta.id}: {datos.email} | "
                f"{datos.nombre_titular} {datos.apellido_titular} | "
                f"{venta.estado}"
            )

        ventas = list(
            db.scalars(
                select(Venta)
                .where(Venta.email.in_(DEMO_EMAILS))
                .order_by(Venta.id)
            ).all()
        )

    pendientes = [
        venta
        for venta in ventas
        if venta.estado == EstadoVenta.PENDIENTE_VERIFICACION.value
    ]
    print(
        f"\nTotal demo: {len(ventas)} ventas; "
        f"{len(pendientes)} pendientes de verificación."
    )
    if len(ventas) != len(DEMO_EMAILS):
        raise RuntimeError(
            "No se encontraron las cuatro ventas demo esperadas."
        )
    if len(pendientes) != len(DEMO_EMAILS):
        print(
            "Advertencia: alguna venta demo ya fue auditada. "
            "Para reiniciar la demo, eliminá ventas.db o esas ventas."
        )
    return len(ventas)


if __name__ == "__main__":
    cargar_demo()
