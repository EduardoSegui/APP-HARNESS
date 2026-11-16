"""Tests del servidor MCP y de las transiciones de estado (F06)."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy import select

from ventas_app.database import SessionLocal
from ventas_app.mcp_server import (
    actualizar_estado_venta,
    listar_ventas_pendientes,
    obtener_detalle_venta,
    servidor_mcp,
)
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


def test_servidor_expone_las_tres_herramientas() -> None:
    herramientas = asyncio.run(servidor_mcp.list_tools())
    por_nombre = {herramienta.name: herramienta for herramienta in herramientas}

    assert set(por_nombre) == {
        "listar_ventas_pendientes",
        "obtener_detalle_venta",
        "actualizar_estado_venta",
    }

    actualizar = por_nombre["actualizar_estado_venta"]
    assert actualizar.input_schema["properties"]["estado"]["enum"] == [
        "APROBADA",
        "OBSERVADA",
    ]
    assert "venta_id" in actualizar.input_schema["required"]
    assert "estado" in actualizar.input_schema["required"]
    assert (
        actualizar.input_schema["properties"]["observaciones"]["default"] is None
    )
    assert all(herramienta.description for herramienta in herramientas)


def test_listar_ventas_pendientes_sin_ventas(client: TestClient) -> None:
    assert listar_ventas_pendientes() == []


def test_listar_ventas_pendientes_devuelve_solo_ventas_pendientes(
    client: TestClient,
) -> None:
    primera = _crear_venta(client, plan="Plan Integral")
    segunda = _crear_venta(
        client,
        plan="Plan Esencial",
        cantidad_adherentes=1,
    )
    procesada = _crear_venta(client)
    actualizar_estado_venta(procesada["id"], "APROBADA")

    pendientes = listar_ventas_pendientes()

    assert [venta["id"] for venta in pendientes] == [
        primera["id"],
        segunda["id"],
    ]
    assert set(pendientes[0]) == {
        "id",
        "titular",
        "plan",
        "precio_total",
        "creado_en",
    }
    assert pendientes[0]["titular"] == "Ana Pérez"
    assert pendientes[0]["plan"] == "Plan Integral"
    assert pendientes[0]["precio_total"] == 78_000
    assert pendientes[1]["plan"] == "Plan Esencial"
    assert pendientes[1]["precio_total"] == 75_000
    assert datetime.fromisoformat(pendientes[0]["creado_en"])
    json.dumps(pendientes)


def test_obtener_detalle_venta_devuelve_todos_los_datos(
    client: TestClient,
) -> None:
    creada = _crear_venta(
        client,
        plan="Plan Integral",
        cantidad_adherentes=2,
    )

    detalle = obtener_detalle_venta(creada["id"])

    assert detalle["id"] == creada["id"]
    assert detalle["nombre_titular"] == "Ana"
    assert detalle["apellido_titular"] == "Pérez"
    assert detalle["dni_titular"] == "30111222"
    assert date.fromisoformat(detalle["fecha_nacimiento_titular"]) == date(
        1990, 5, 20
    )
    assert detalle["email"] == "ana.perez@example.com"
    assert detalle["telefono"] == "+54 11 5555-5555"
    assert detalle["calle"] == "Av. Corrientes"
    assert detalle["altura"] == "1234"
    assert detalle["piso_depto"] == "2 B"
    assert detalle["localidad"] == "Ciudad Autónoma de Buenos Aires"
    assert detalle["provincia"] == "Ciudad Autónoma de Buenos Aires"
    assert detalle["codigo_postal"] == "1043"
    assert detalle["plan"]["nombre"] == "Plan Integral"
    assert detalle["precio_total"] == 182_000
    assert detalle["estado"] == "PENDIENTE_VERIFICACION"
    assert detalle["observaciones"] is None
    assert len(detalle["integrantes"]) == 2
    assert detalle["integrantes"][0]["dni"] == "40111001"
    assert detalle["integrantes"][1]["dni"] == "40111002"
    assert datetime.fromisoformat(detalle["creado_en"])
    assert datetime.fromisoformat(detalle["actualizado_en"])
    json.dumps(detalle)


def test_obtener_detalle_venta_inexistente_es_error() -> None:
    with pytest.raises(ToolError, match="La venta 999999 no existe"):
        obtener_detalle_venta(999999)


def test_listar_ventas_pendientes_incluye_plan_inactivo(
    client: TestClient,
) -> None:
    creada = _crear_venta(client, plan="Plan Superior")

    with SessionLocal() as db:
        plan = db.scalar(select(Plan).where(Plan.nombre == "Plan Superior"))
        assert plan is not None
        plan.activo = False
        db.commit()

    pendientes = listar_ventas_pendientes()
    detalle = obtener_detalle_venta(creada["id"])

    assert [venta["id"] for venta in pendientes] == [creada["id"]]
    assert detalle["plan"]["nombre"] == "Plan Superior"
    assert detalle["plan"]["activo"] is False


def test_actualizar_estado_venta_aprueba_y_limpia_observaciones(
    client: TestClient,
) -> None:
    creada = _crear_venta(client)

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        venta.observaciones = "Observación previa que debe limpiarse."
        db.commit()

    actualizada = actualizar_estado_venta(
        creada["id"],
        "APROBADA",
        "Este texto no debe persistirse.",
    )

    assert actualizada["estado"] == "APROBADA"
    assert actualizada["observaciones"] is None

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "APROBADA"
        assert venta.observaciones is None


def test_actualizar_estado_venta_observa_y_normaliza_observaciones(
    client: TestClient,
) -> None:
    creada = _crear_venta(client)
    texto = "R1: El titular no cumple la edad mínima.\nR2: DNI duplicado."

    actualizada = actualizar_estado_venta(
        creada["id"],
        "OBSERVADA",
        f"  {texto}  ",
    )

    assert actualizada["estado"] == "OBSERVADA"
    assert actualizada["observaciones"] == texto
    assert listar_ventas_pendientes() == []

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "OBSERVADA"
        assert venta.observaciones == texto


@pytest.mark.parametrize(
    "observaciones",
    [None, "", "   ", "\n\t "],
)
def test_actualizar_estado_venta_observada_exige_observaciones(
    client: TestClient,
    observaciones: str | None,
) -> None:
    creada = _crear_venta(client)

    with pytest.raises(ToolError, match="requiere al menos una observación"):
        actualizar_estado_venta(
            creada["id"],
            "OBSERVADA",
            observaciones,
        )

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "PENDIENTE_VERIFICACION"
        assert venta.observaciones is None


@pytest.mark.parametrize(
    "estado",
    ["PENDIENTE_VERIFICACION", "CANCELADA", "aprobada"],
)
def test_actualizar_estado_venta_rechaza_estado_destino_invalido(
    client: TestClient,
    estado: str,
) -> None:
    creada = _crear_venta(client)

    with pytest.raises(ToolError, match="Estado inválido"):
        actualizar_estado_venta(creada["id"], estado)  # type: ignore[arg-type]

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "PENDIENTE_VERIFICACION"
        assert venta.observaciones is None


def test_actualizar_estado_venta_no_permite_reabrir_una_venta_aprobada(
    client: TestClient,
) -> None:
    creada = _crear_venta(client)
    actualizar_estado_venta(creada["id"], "APROBADA")

    with pytest.raises(ToolError, match="no admite nuevas transiciones"):
        actualizar_estado_venta(
            creada["id"],
            "OBSERVADA",
            "R1: Intento de modificar una venta ya procesada.",
        )

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "APROBADA"
        assert venta.observaciones is None


def test_actualizar_estado_venta_inexistente_es_error() -> None:
    with pytest.raises(ToolError, match="La venta 999999 no existe"):
        actualizar_estado_venta(999999, "APROBADA")
