"""Tests del panel HTML de ventas (F05)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from ventas_app.database import SessionLocal
from ventas_app.models import Plan, Venta


def _obtener_plan_id(nombre: str) -> int:
    with SessionLocal() as db:
        plan_id = db.scalar(select(Plan.id).where(Plan.nombre == nombre))

    assert plan_id is not None, f"No existe el plan {nombre}"
    return plan_id


def _crear_venta(
    client: TestClient,
    *,
    plan: str = "Plan Integral",
    cantidad_adherentes: int = 0,
) -> dict[str, Any]:
    integrantes = [
        {
            "nombre": f"Adherente {indice}",
            "apellido": "Pérez",
            "dni": str(40_111_000 + indice),
            "fecha_nacimiento": "2010-03-15",
            "parentesco": "Hijo/a",
        }
        for indice in range(1, cantidad_adherentes + 1)
    ]
    respuesta = client.post(
        "/api/ventas",
        json={
            "nombre_titular": "Ana",
            "apellido_titular": "Pérez",
            "dni_titular": "30111222",
            "fecha_nacimiento_titular": "1990-05-20",
            "email": "ana.perez@example.com",
            "telefono": "+54 11 5555-5555",
            "calle": "Av. Corrientes",
            "altura": "1234",
            "piso_depto": "2 B",
            "localidad": "Ciudad Autónoma de Buenos Aires",
            "provincia": "Ciudad Autónoma de Buenos Aires",
            "codigo_postal": "1043",
            "plan_id": _obtener_plan_id(plan),
            "integrantes": integrantes,
        },
    )

    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_panel_sin_ventas_muestra_estado_vacio(client: TestClient) -> None:
    respuesta = client.get("/ventas")

    assert respuesta.status_code == 200
    assert "text/html" in respuesta.headers["content-type"]

    html = respuesta.text

    assert "Panel de ventas" in html
    assert "Todavía no hay ventas registradas" in html
    assert "Cargar primera venta" in html
    assert "<table" not in html


def test_panel_lista_venta_con_todos_los_datos(client: TestClient) -> None:
    venta = _crear_venta(client, plan="Plan Integral", cantidad_adherentes=2)

    html = client.get("/ventas").text

    assert 'class="min-w-full' in html
    assert f'id="venta-{venta["id"]}"' in html
    assert "Ana Pérez" in html
    assert "Plan Integral" in html
    assert 'data-cantidad-integrantes="2"' in html
    assert "$182.000" in html
    assert 'data-estado="PENDIENTE_VERIFICACION"' in html
    assert "bg-amber-100" in html
    assert "1 venta registrada" in html


def test_panel_ordena_ventas_de_mas_reciente_a_mas_antigua(client: TestClient) -> None:
    antigua = _crear_venta(client, plan="Plan Esencial")
    reciente = _crear_venta(client, plan="Plan Integral")

    with SessionLocal() as db:
        venta_antigua = db.get(Venta, antigua["id"])
        venta_reciente = db.get(Venta, reciente["id"])
        assert venta_antigua is not None
        assert venta_reciente is not None
        venta_antigua.creado_en = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        venta_reciente.creado_en = datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)
        db.commit()

    html = client.get("/ventas").text

    indice_reciente = html.index(f'id="venta-{reciente["id"]}"')
    indice_antigua = html.index(f'id="venta-{antigua["id"]}"')

    assert indice_reciente < indice_antigua


def test_panel_muestra_los_badges_de_los_tres_estados(client: TestClient) -> None:
    pendiente = _crear_venta(client)
    aprobada = _crear_venta(client)
    observada = _crear_venta(client)

    with SessionLocal() as db:
        venta_pendiente = db.get(Venta, pendiente["id"])
        venta_aprobada = db.get(Venta, aprobada["id"])
        venta_observada = db.get(Venta, observada["id"])
        assert venta_pendiente is not None
        assert venta_aprobada is not None
        assert venta_observada is not None
        venta_aprobada.estado = "APROBADA"
        venta_aprobada.observaciones = None
        venta_observada.estado = "OBSERVADA"
        venta_observada.observaciones = "R1: El titular no cumple la edad mínima."
        db.commit()

    html = client.get("/ventas").text

    assert 'data-estado="PENDIENTE_VERIFICACION"' in html
    assert "bg-amber-100" in html
    assert 'data-estado="APROBADA"' in html
    assert "bg-green-100" in html
    assert 'data-estado="OBSERVADA"' in html
    assert "bg-red-100" in html
    assert "3 ventas registradas" in html


def test_panel_muestra_ventas_con_plan_inactivo(client: TestClient) -> None:
    venta = _crear_venta(client, plan="Plan Superior")

    with SessionLocal() as db:
        plan = db.get(Plan, venta["plan_id"])
        assert plan is not None
        plan.activo = False
        db.commit()

    html = client.get("/ventas").text

    assert f'id="venta-{venta["id"]}"' in html
    assert "Plan Superior" in html


def test_comprobante_enlaza_al_panel_de_ventas(client: TestClient) -> None:
    html = client.get("/").text

    assert 'id="enlace-panel-ventas"' in html
    assert 'href="/ventas"' in html
    assert "Ir al panel de ventas" in html
