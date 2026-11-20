"""Tests del tablero ejecutivo y las exportaciones (F19)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from ventas_app.database import SessionLocal
from ventas_app.models import Plan
from ventas_app.services.estados import cambiar_estado_venta


def _plan_id(nombre: str) -> int:
    with SessionLocal() as db:
        plan_id = db.scalar(select(Plan.id).where(Plan.nombre == nombre))
    assert plan_id is not None
    return plan_id


def _payload(
    plan: str,
    *,
    dni: str,
    email: str,
    medio_pago: str = "PAGO_FACIL",
    regimen: str = "PARTICULAR",
    cuil: str | None = None,
    aporte: int = 0,
    adherentes: int = 0,
) -> dict[str, Any]:
    integrantes = [
        {
            "nombre": f"Adherente {indice}",
            "apellido": "Pérez",
            "dni": str(41_000_000 + indice),
            "fecha_nacimiento": "2010-03-15",
            "parentesco": "Hijo/a",
        }
        for indice in range(1, adherentes + 1)
    ]
    datos: dict[str, Any] = {
        "nombre_titular": "Ana",
        "apellido_titular": "Pérez",
        "dni_titular": dni,
        "fecha_nacimiento_titular": "1990-05-20",
        "email": email,
        "telefono": "1145678901",
        "calle": "Av. Corrientes",
        "altura": "1234",
        "piso_depto": None,
        "localidad": "Ciudad Autónoma de Buenos Aires",
        "provincia": "Ciudad Autónoma de Buenos Aires",
        "codigo_postal": "1043",
        "plan_id": _plan_id(plan),
        "medio_pago": medio_pago,
        "regimen_afiliacion": regimen,
        "cuil_titular": cuil,
        "aporte_estimado": aporte,
        "ddjj": {
            "preexistencias": False,
            "internaciones_ultimos_12m": False,
            "embarazo_actual": False,
            "medicacion_cronica": False,
            "discapacidad_declarada": False,
            "detalle": None,
            "declaracion_confirmada": True,
        },
        "integrantes": integrantes,
    }
    if medio_pago == "TARJETA_CREDITO":
        datos["tarjeta"] = {
            "marca": "VISA",
            "numero": "4111111111111111",
            "titular": "Ana Pérez",
            "vencimiento": "12/99",
            "cvv": "123",
        }
    elif medio_pago == "CBU":
        datos["cbu"] = {
            "numero": "0170099220000067890123",
            "entidad": "Banco Ejemplo",
            "titular": "Ana Pérez",
            "cuil": cuil or "20123456789",
        }
    return datos


def _crear(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    respuesta = client.post("/api/ventas", json=_payload(**kwargs))
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _preparar_datos(client: TestClient) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    aprobada = _crear(
        client,
        plan="Plan Integral",
        dni="30111222",
        email="aprobada@example.com",
        medio_pago="TARJETA_CREDITO",
        adherentes=1,
    )
    observada = _crear(
        client,
        plan="Plan Esencial",
        dni="30111223",
        email="observada@example.com",
        medio_pago="CBU",
        regimen="RELACION_DEPENDENCIA",
        cuil="20123456789",
        aporte=5_000,
    )
    pendiente = _crear(
        client,
        plan="Plan Superior",
        dni="30111224",
        email="pendiente@example.com",
    )
    with SessionLocal() as db:
        cambiar_estado_venta(db, aprobada["id"], "APROBADA")
        cambiar_estado_venta(
            db,
            observada["id"],
            "OBSERVADA",
            "R1: El titular no cumple la edad mínima.",
        )
    return aprobada, observada, pendiente


def test_metricas_ejecutivas(client: TestClient) -> None:
    _preparar_datos(client)

    respuesta = client.get("/api/metricas")

    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["total_ventas"] == 3
    assert datos["pendientes"] == 1
    assert datos["aprobadas"] == 1
    assert datos["observadas"] == 1
    assert datos["tasa_aprobacion"] == 33.33
    assert datos["personas_cubiertas"] == 2
    assert datos["mrr_bruto"] == 130_000
    assert datos["descuentos"] == 39_000
    assert datos["aportes"] == 0
    assert datos["recaudacion_neta"] == 91_000
    assert datos["ticket_promedio"] == 91_000
    assert datos["por_plan"][0]["etiqueta"] == "Plan Integral"
    assert datos["por_medio_pago"][0]["etiqueta"] == "Tarjeta de crédito"
    assert any(
        motivo["codigo"] == "R1" and motivo["cantidad"] == 1
        for motivo in datos["motivos_observacion"]
    )


def test_metricas_redondean_descuentos_por_venta(client: TestClient) -> None:
    ventas = [
        _crear(
            client,
            plan="Plan Integral",
            dni="30111301",
            email="a1@example.com",
            medio_pago="TARJETA_CREDITO",
            adherentes=1,
        ),
        _crear(
            client,
            plan="Plan Esencial",
            dni="30111302",
            email="a2@example.com",
            medio_pago="CBU",
            regimen="RELACION_DEPENDENCIA",
            cuil="20123456789",
            aporte=15_000,
        ),
        _crear(
            client,
            plan="Plan Esencial",
            dni="30111303",
            email="a3@example.com",
        ),
    ]
    with SessionLocal() as db:
        for venta in ventas:
            cambiar_estado_venta(db, venta["id"], "APROBADA")

    datos = client.get("/api/metricas").json()

    assert datos["mrr_bruto"] == 220_000
    assert datos["descuentos"] == 48_000
    assert datos["aportes"] == 15_000
    assert datos["recaudacion_neta"] == 157_000
    assert (
        datos["mrr_bruto"]
        - datos["descuentos"]
        - datos["aportes"]
        == datos["recaudacion_neta"]
    )


def test_metricas_filtran_por_plan_y_fecha(client: TestClient) -> None:
    aprobada, _, _ = _preparar_datos(client)
    plan_id = aprobada["plan_id"]

    por_plan = client.get("/api/metricas", params={"plan_id": plan_id})
    assert por_plan.status_code == 200
    assert por_plan.json()["total_ventas"] == 1

    futuro = client.get("/api/metricas", params={"desde": "2099-01-01"})
    assert futuro.status_code == 200
    assert futuro.json()["total_ventas"] == 0


def test_dashboard_renderiza_kpis(client: TestClient) -> None:
    _preparar_datos(client)

    respuesta = client.get("/dashboard")

    assert respuesta.status_code == 200
    html = respuesta.text
    assert "Tablero ejecutivo" in html
    assert "MRR bruto" in html
    assert "Recaudación neta" in html
    assert "Motivos de observación" in html
    assert "$130.000" in html
    assert "R1" in html
    assert "Tablero" in html


def test_exportacion_padron_csv_y_json(client: TestClient) -> None:
    aprobada, _, _ = _preparar_datos(client)

    csv_response = client.get("/api/exportar/padron", params={"formato": "csv"})
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "attachment; filename=\"padron.csv\"" == (
        csv_response.headers["content-disposition"]
    )
    assert "ID;Titular;DNI;" in csv_response.text
    assert "Plan Integral" in csv_response.text
    assert "Plan Esencial" not in csv_response.text
    assert "4111111111111111" not in csv_response.text

    json_response = client.get("/api/exportar/padron", params={"formato": "json"})
    assert json_response.status_code == 200
    datos = json_response.json()
    assert len(datos) == 1
    assert datos[0]["ID"] == aprobada["id"]
    assert "4111111111111111" not in json_response.text


def test_metricas_y_exportacion_sin_datos(client: TestClient) -> None:
    metricas = client.get("/api/metricas")
    assert metricas.status_code == 200
    datos = metricas.json()
    assert datos["total_ventas"] == 0
    assert datos["tasa_aprobacion"] == 0
    assert datos["mrr_bruto"] == 0

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Sin ventas aprobadas" in dashboard.text

    padron = client.get("/api/exportar/padron?formato=csv")
    assert padron.status_code == 200
    assert padron.text.strip().endswith("Fecha de alta")
    assert len(padron.text.strip().splitlines()) == 1

    json_padron = client.get("/api/exportar/padron?formato=json")
    assert json_padron.json() == []


def test_exportacion_cobranzas_y_formato_invalido(client: TestClient) -> None:
    _preparar_datos(client)

    respuesta = client.get(
        "/api/exportar/cobranzas",
        params={"formato": "csv"},
    )

    assert respuesta.status_code == 200
    assert "text/csv" in respuesta.headers["content-type"]
    assert "Total a cobrar" in respuesta.text
    assert "Plan Integral" in respuesta.text
    assert "Plan Esencial" not in respuesta.text

    invalido = client.get(
        "/api/exportar/cobranzas",
        params={"formato": "xml"},
    )
    assert invalido.status_code == 422
