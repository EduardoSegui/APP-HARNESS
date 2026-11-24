"""Tests del linaje de ventas y sus eventos (F18)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ventas_app.database import SessionLocal
from ventas_app.models import Plan, TipoEventoVenta, VentaEvento
from ventas_app.services.estados import cambiar_estado_venta
from ventas_app.services.eventos import listar_eventos


def _plan_id(nombre: str) -> int:
    with SessionLocal() as db:
        plan_id = db.scalar(select(Plan.id).where(Plan.nombre == nombre))
    assert plan_id is not None
    return plan_id


def _payload(plan_id: int) -> dict[str, Any]:
    return {
        "nombre_titular": "Ana",
        "apellido_titular": "Pérez",
        "dni_titular": "30111222",
        "fecha_nacimiento_titular": "1990-05-20",
        "email": "ana.eventos@example.com",
        "telefono": "1145678901",
        "calle": "Av. Corrientes",
        "altura": "1234",
        "piso_depto": None,
        "localidad": "Ciudad Autónoma de Buenos Aires",
        "provincia": "Ciudad Autónoma de Buenos Aires",
        "codigo_postal": "1043",
        "plan_id": plan_id,
        "medio_pago": "PAGO_FACIL",
        "version": 1,
        "ddjj": {
            "preexistencias": False,
            "internaciones_ultimos_12m": False,
            "embarazo_actual": False,
            "medicacion_cronica": False,
            "discapacidad_declarada": False,
            "detalle": None,
            "declaracion_confirmada": True,
        },
        "integrantes": [],
    }


def _crear_venta(client: TestClient) -> dict[str, Any]:
    respuesta = client.post(
        "/api/ventas",
        json=_payload(_plan_id("Plan Integral")),
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _tipos(venta_id: int) -> list[str]:
    with SessionLocal() as db:
        return [evento.tipo for evento in listar_eventos(db, venta_id)]


def test_creacion_registra_evento(client: TestClient) -> None:
    venta = _crear_venta(client)

    with SessionLocal() as db:
        eventos = listar_eventos(db, venta["id"])

    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.tipo == TipoEventoVenta.CREADA.value
    assert evento.actor == "admin-test"
    assert evento.estado_anterior is None
    assert evento.estado_nuevo == "PENDIENTE_VERIFICACION"
    assert "Plan Integral" in (evento.detalle or "")


def test_edicion_registra_evento_en_orden(client: TestClient) -> None:
    venta = _crear_venta(client)

    respuesta = client.put(
        f"/api/ventas/{venta['id']}",
        json=_payload(_plan_id("Plan Esencial")),
    )
    assert respuesta.status_code == 200, respuesta.text

    assert _tipos(venta["id"]) == [
        TipoEventoVenta.EDITADA.value,
        TipoEventoVenta.CREADA.value,
    ]

    with SessionLocal() as db:
        evento = listar_eventos(db, venta["id"])[0]
    assert evento.actor == "admin-test"
    assert evento.estado_anterior == "PENDIENTE_VERIFICACION"
    assert evento.estado_nuevo == "PENDIENTE_VERIFICACION"
    assert "Plan Esencial" in (evento.detalle or "")


def test_eventos_redactan_pii_en_observaciones(client: TestClient) -> None:
    venta = _crear_venta(client)
    with SessionLocal() as db:
        cambiar_estado_venta(
            db,
            venta["id"],
            "OBSERVADA",
            "R2: DNI 30111222 repetido; email ana.eventos@example.com.",
        )
        evento = listar_eventos(db, venta["id"])[0]
        assert "30111222" not in (evento.detalle or "")
        assert "ana.eventos@example.com" not in (evento.detalle or "")
        assert "***" in (evento.detalle or "")


def test_auditoria_registra_evento(client: TestClient) -> None:
    venta = _crear_venta(client)

    with SessionLocal() as db:
        cambiar_estado_venta(db, venta["id"], "APROBADA")

    assert _tipos(venta["id"]) == [
        TipoEventoVenta.AUDITADA_APROBADA.value,
        TipoEventoVenta.CREADA.value,
    ]

    with SessionLocal() as db:
        evento = listar_eventos(db, venta["id"])[0]
    assert evento.actor == "auditor"
    assert evento.estado_anterior == "PENDIENTE_VERIFICACION"
    assert evento.estado_nuevo == "APROBADA"


def test_api_eventos_devuelve_linaje_y_404(client: TestClient) -> None:
    venta = _crear_venta(client)

    respuesta = client.get(f"/api/ventas/{venta['id']}/eventos")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert len(datos) == 1
    assert datos[0]["tipo"] == "CREADA"

    inexistente = client.get("/api/ventas/999999/eventos")
    assert inexistente.status_code == 404


def test_rollback_de_edicion_no_deja_evento_falso(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    venta = _crear_venta(client)
    payload = _payload(_plan_id("Plan Esencial"))

    def commit_falla(_self: object) -> None:
        raise RuntimeError("fallo simulado de commit")

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", commit_falla)
    with pytest.raises(RuntimeError, match="fallo simulado de commit"):
        client.put(f"/api/ventas/{venta['id']}", json=payload)
    monkeypatch.undo()

    with SessionLocal() as db:
        total = db.scalar(
            select(func.count())
            .select_from(VentaEvento)
            .where(VentaEvento.venta_id == venta["id"])
        )
    assert total == 1
    assert _tipos(venta["id"]) == [TipoEventoVenta.CREADA.value]
