"""Tests de integración de la API REST de ventas."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ventas_app.database import SessionLocal
from ventas_app.models import Integrante, Plan, Venta


def obtener_plan_id(nombre: str) -> int:
    with SessionLocal() as db:
        plan_id = db.scalar(select(Plan.id).where(Plan.nombre == nombre))

    assert plan_id is not None, f"No existe el plan {nombre}"
    return plan_id


def payload_venta(
    plan_id: int,
    cantidad_adherentes: int = 0,
    **overrides: Any,
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
    datos: dict[str, Any] = {
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
        "plan_id": plan_id,
        "medio_pago": "PAGO_FACIL",
        "integrantes": integrantes,
    }
    datos.update(overrides)
    return datos


@pytest.mark.parametrize(
    ("nombre_plan", "cantidad_adherentes", "total_esperado"),
    [
        ("Plan Esencial", 0, 45_000),
        ("Plan Esencial", 2, 105_000),
        ("Plan Integral", 1, 130_000),
        ("Plan Integral", 2, 182_000),
        ("Plan Superior", 3, 380_000),
    ],
)
def test_crear_venta_calcula_el_total_en_el_servidor(
    client: TestClient,
    nombre_plan: str,
    cantidad_adherentes: int,
    total_esperado: int,
) -> None:
    plan_id = obtener_plan_id(nombre_plan)

    respuesta = client.post(
        "/api/ventas",
        json=payload_venta(plan_id, cantidad_adherentes),
    )

    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    assert datos["id"] > 0
    assert datos["precio_total"] == total_esperado
    assert datos["subtotal_base"] == total_esperado
    assert datos["descuento_porcentaje"] == 0
    assert datos["medio_pago"] == "PAGO_FACIL"
    assert datos["plan"]["nombre"] == nombre_plan
    assert datos["estado"] == "PENDIENTE_VERIFICACION"
    assert datos["observaciones"] is None
    assert len(datos["integrantes"]) == cantidad_adherentes
    assert datos["creado_en"] is not None
    assert datos["actualizado_en"] is not None


def test_crear_venta_persiste_venta_e_integrantes(client: TestClient) -> None:
    plan_id = obtener_plan_id("Plan Integral")

    respuesta = client.post(
        "/api/ventas",
        json=payload_venta(plan_id, 2),
    )

    assert respuesta.status_code == 201, respuesta.text
    venta_id = respuesta.json()["id"]

    with SessionLocal() as db:
        venta = db.get(Venta, venta_id)

        assert venta is not None
        assert venta.precio_total == 182_000
        assert venta.plan_id == plan_id
        assert venta.plan.nombre == "Plan Integral"
        assert venta.estado == "PENDIENTE_VERIFICACION"
        assert len(venta.integrantes) == 2
        assert {integrante.dni for integrante in venta.integrantes} == {
            "40111001",
            "40111002",
        }


def test_get_venta_devuelve_el_detalle(client: TestClient) -> None:
    plan_id = obtener_plan_id("Plan Superior")
    creada = client.post(
        "/api/ventas",
        json=payload_venta(plan_id, 1),
    )
    assert creada.status_code == 201, creada.text
    venta_id = creada.json()["id"]

    respuesta = client.get(f"/api/ventas/{venta_id}")

    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["id"] == venta_id
    assert datos["nombre_titular"] == "Ana"
    assert datos["plan"]["nombre"] == "Plan Superior"
    assert datos["precio_total"] == 210_000
    assert len(datos["integrantes"]) == 1
    assert datos["integrantes"][0]["dni"] == "40111001"


def test_get_venta_inexistente_devuelve_404(client: TestClient) -> None:
    respuesta = client.get("/api/ventas/999999")

    assert respuesta.status_code == 404
    assert "no existe" in respuesta.json()["detail"]


def test_plan_inexistente_devuelve_400(client: TestClient) -> None:
    respuesta = client.post(
        "/api/ventas",
        json=payload_venta(999_999),
    )

    assert respuesta.status_code == 400
    assert "no existe" in respuesta.json()["detail"]


def test_plan_inactivo_devuelve_400(client: TestClient) -> None:
    with SessionLocal() as db:
        plan = db.scalar(select(Plan).where(Plan.nombre == "Plan Esencial"))
        assert plan is not None
        plan.activo = False
        db.commit()
        plan_id = plan.id

    respuesta = client.post(
        "/api/ventas",
        json=payload_venta(plan_id),
    )

    assert respuesta.status_code == 400
    assert "no está activo" in respuesta.json()["detail"]


def test_precio_total_usa_los_precios_vigentes_de_la_base(
    client: TestClient,
) -> None:
    with SessionLocal() as db:
        plan = db.scalar(select(Plan).where(Plan.nombre == "Plan Integral"))
        assert plan is not None
        plan.precio_titular = 99_000
        plan.precio_adherente = 1_000
        db.commit()
        plan_id = plan.id

    respuesta = client.post(
        "/api/ventas",
        json=payload_venta(plan_id, 2),
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["precio_total"] == 101_000


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("precio_total", 1),
        ("estado", "APROBADA"),
        ("observaciones", "dato impuesto por el cliente"),
    ],
)
def test_cliente_no_puede_imponer_campos_del_servidor(
    client: TestClient,
    campo: str,
    valor: object,
) -> None:
    plan_id = obtener_plan_id("Plan Esencial")
    payload = payload_venta(plan_id)
    payload[campo] = valor

    respuesta = client.post("/api/ventas", json=payload)

    assert respuesta.status_code == 422


def test_dni_duplicado_en_grupo_familiar_devuelve_422(
    client: TestClient,
) -> None:
    plan_id = obtener_plan_id("Plan Esencial")
    payload = payload_venta(plan_id, 1)
    payload["integrantes"][0]["dni"] = payload["dni_titular"]

    respuesta = client.post("/api/ventas", json=payload)

    assert respuesta.status_code == 422


def test_codigo_postal_invalido_devuelve_422(client: TestClient) -> None:
    plan_id = obtener_plan_id("Plan Esencial")
    payload = payload_venta(plan_id, codigo_postal="C1043")

    respuesta = client.post("/api/ventas", json=payload)

    assert respuesta.status_code == 422


def test_plan_id_invalido_devuelve_422(client: TestClient) -> None:
    respuesta = client.post(
        "/api/ventas",
        json=payload_venta(0),
    )

    assert respuesta.status_code == 422


def test_error_de_commit_no_deja_registros_parciales(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_id = obtener_plan_id("Plan Integral")
    payload = payload_venta(plan_id, 2)

    def commit_falla(_self: object) -> None:
        raise RuntimeError("fallo simulado de commit")

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", commit_falla)

    with pytest.raises(RuntimeError, match="fallo simulado de commit"):
        client.post("/api/ventas", json=payload)

    monkeypatch.undo()

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Venta)) == 0
        assert db.scalar(select(func.count()).select_from(Integrante)) == 0


def test_crear_venta_con_descuento_tarjeta_credito(client: TestClient) -> None:
    plan_id = obtener_plan_id("Plan Esencial")
    # Plan Esencial: 45_000 -> 30% desc = 13_500 -> total = 31_500
    payload = payload_venta(plan_id, 0, medio_pago="TARJETA_CREDITO")

    respuesta = client.post("/api/ventas", json=payload)
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["medio_pago"] == "TARJETA_CREDITO"
    assert datos["subtotal_base"] == 45_000
    assert datos["descuento_porcentaje"] == 30
    assert datos["precio_total"] == 31_500


def test_crear_venta_con_descuento_cbu(client: TestClient) -> None:
    plan_id = obtener_plan_id("Plan Integral")
    # Plan Integral con 1 adherente: 78_000 + 52_000 = 130_000 -> 20% desc = 26_000 -> total = 104_000
    payload = payload_venta(plan_id, 1, medio_pago="CBU")

    respuesta = client.post("/api/ventas", json=payload)
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["medio_pago"] == "CBU"
    assert datos["subtotal_base"] == 130_000
    assert datos["descuento_porcentaje"] == 20
    assert datos["precio_total"] == 104_000


def test_crear_venta_con_medio_pago_invalido_devuelve_422(client: TestClient) -> None:
    plan_id = obtener_plan_id("Plan Esencial")
    payload = payload_venta(plan_id, 0, medio_pago="METODO_INEXISTENTE")

    respuesta = client.post("/api/ventas", json=payload)
    assert respuesta.status_code == 422

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Venta)) == 0
        assert db.scalar(select(func.count()).select_from(Integrante)) == 0


def test_crear_venta_sin_medio_pago_devuelve_422(client: TestClient) -> None:
    plan_id = obtener_plan_id("Plan Esencial")
    payload = payload_venta(plan_id, 0)
    payload.pop("medio_pago")

    respuesta = client.post("/api/ventas", json=payload)
    assert respuesta.status_code == 422

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Venta)) == 0
        assert db.scalar(select(func.count()).select_from(Integrante)) == 0
