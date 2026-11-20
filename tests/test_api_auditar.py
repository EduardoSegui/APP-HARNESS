"""Tests del endpoint POST /api/auditar y de la trazabilidad MCP (F08)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ventas_app import auditor as modulo_auditor
from ventas_app.auditor import ErrorMCP, ResultadoLLM
from ventas_app.database import SessionLocal
from ventas_app.models import Plan, Venta


def _obtener_plan_id(nombre: str = "Plan Integral") -> int:
    with SessionLocal() as db:
        plan_id = db.scalar(select(Plan.id).where(Plan.nombre == nombre))
    assert plan_id is not None, f"No existe el plan {nombre}"
    return plan_id


def _crear_venta(
    client: TestClient,
    *,
    fecha_titular: str | None = None,
) -> dict[str, Any]:
    if fecha_titular is None:
        fecha_titular = "1990-05-20"

    respuesta = client.post(
        "/api/ventas",
        json={
            "nombre_titular": "Ana",
            "apellido_titular": "Pérez",
            "dni_titular": "30111222",
            "fecha_nacimiento_titular": fecha_titular,
            "email": "ana.perez@example.com",
            "telefono": "+54 11 5555-5555",
            "calle": "Av. Corrientes",
            "altura": "1234",
            "piso_depto": "2 B",
            "localidad": "Ciudad Autónoma de Buenos Aires",
            "provincia": "Ciudad Autónoma de Buenos Aires",
            "codigo_postal": "1043",
            "plan_id": _obtener_plan_id(),
            "medio_pago": "PAGO_FACIL",
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
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _mock_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        modulo_auditor,
        "generar_resumen_llm",
        lambda aprobadas, observadas, errores: ResultadoLLM(
            resumen="Resumen narrativo de prueba.",
            ok=True,
        ),
    )


def test_post_auditar_procesa_pendientes_y_devuelve_traza(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    creada = _crear_venta(client)
    _mock_llm(monkeypatch)

    respuesta = client.post("/api/auditar")

    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["procesadas"] == 1
    assert datos["aprobadas"] == 1
    assert datos["observadas"] == 0
    assert datos["resumen_llm"] == "Resumen narrativo de prueba."
    assert datos["llm_ok"] is True
    assert datos["advertencia"] is None

    traza = datos["traza_mcp"]
    assert [paso["herramienta"] for paso in traza] == [
        "listar_ventas_pendientes",
        "obtener_detalle_venta",
        "actualizar_estado_venta",
    ]
    assert all(
        set(paso) == {"herramienta", "argumentos", "estado"}
        for paso in traza
    )
    assert traza[0]["argumentos"] == {}
    assert traza[1]["argumentos"] == {"venta_id": creada["id"]}
    assert traza[2]["argumentos"] == {
        "venta_id": creada["id"],
        "estado": "APROBADA",
        "observaciones": None,
    }
    assert all(paso["estado"] == "ok" for paso in traza)

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "APROBADA"
        assert venta.observaciones is None


def test_post_auditar_registra_observaciones_en_la_traza(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valida = _crear_venta(client)
    menor = _crear_venta(
        client,
        fecha_titular=date(date.today().year - 10, 1, 1).isoformat(),
    )
    _mock_llm(monkeypatch)

    respuesta = client.post("/api/auditar")

    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["procesadas"] == 2
    assert datos["aprobadas"] == 1
    assert datos["observadas"] == 1
    assert len(datos["traza_mcp"]) == 5

    actualizaciones = [
        paso
        for paso in datos["traza_mcp"]
        if paso["herramienta"] == "actualizar_estado_venta"
    ]
    por_venta = {
        paso["argumentos"]["venta_id"]: paso["argumentos"]
        for paso in actualizaciones
    }
    assert por_venta[valida["id"]]["estado"] == "APROBADA"
    assert por_venta[valida["id"]]["observaciones"] is None
    assert por_venta[menor["id"]]["estado"] == "OBSERVADA"
    assert "R1: El titular tiene" in (
        por_venta[menor["id"]]["observaciones"] or ""
    )

    with SessionLocal() as db:
        venta_valida = db.get(Venta, valida["id"])
        venta_menor = db.get(Venta, menor["id"])
        assert venta_valida is not None
        assert venta_menor is not None
        assert venta_valida.estado == "APROBADA"
        assert venta_menor.estado == "OBSERVADA"
        assert venta_menor.observaciones is not None
        assert "R1:" in venta_menor.observaciones


def test_post_auditar_sin_pendientes_no_llama_al_llm(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_llamar(*args: Any, **kwargs: Any) -> ResultadoLLM:
        raise AssertionError("No se debe llamar al LLM sin ventas pendientes")

    monkeypatch.setattr(modulo_auditor, "generar_resumen_llm", no_llamar)

    respuesta = client.post("/api/auditar")

    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["procesadas"] == 0
    assert datos["aprobadas"] == 0
    assert datos["observadas"] == 0
    assert datos["resumen_llm"] is None
    assert datos["llm_ok"] is False
    assert datos["advertencia"] == "No hay ventas pendientes para auditar."
    assert datos["traza_mcp"] == [
        {
            "herramienta": "listar_ventas_pendientes",
            "argumentos": {},
            "estado": "ok",
        }
    ]


def test_post_auditar_sin_llm_configurado_usa_resumen_local(
    client: TestClient,
) -> None:
    creada = _crear_venta(client)

    respuesta = client.post("/api/auditar")

    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["procesadas"] == 1
    assert datos["aprobadas"] == 1
    assert datos["resumen_llm"] is None
    assert datos["llm_ok"] is False
    assert "no configurado" in (datos["advertencia"] or "")

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "APROBADA"


def test_post_auditar_error_mcp_devuelve_error_controlado(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fallar() -> dict[str, Any]:
        raise ErrorMCP("servidor no disponible")

    monkeypatch.setattr(
        "ventas_app.routers.api.ejecutar_auditoria",
        fallar,
    )

    respuesta = client.post("/api/auditar")

    assert respuesta.status_code == 500
    assert respuesta.json() == {
        "detail": "No se pudo ejecutar la auditoría."
    }
