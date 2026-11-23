"""Tests de hardening HTTP y anti-abuso (F24)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from ventas_app.middleware import _politica, _SlidingLimiter
from ventas_app.routers import api as api_module
from ventas_app.services import exportacion


def _payload(plan_id: int = 1, **overrides: Any) -> dict[str, Any]:
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
    datos.update(overrides)
    return datos


def test_headers_de_seguridad_y_no_cache(client: TestClient) -> None:
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert "default-src 'self'" in respuesta.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in respuesta.headers["content-security-policy"]
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    assert respuesta.headers["x-frame-options"] == "DENY"
    assert respuesta.headers["referrer-policy"] == "no-referrer"
    assert respuesta.headers["x-robots-tag"] == "noindex, nofollow"
    assert respuesta.headers["cache-control"] == "no-store"


def test_docs_cerrados_por_defecto(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_422_no_expone_tarjeta_ni_cbu(client: TestClient) -> None:
    tarjeta = {
        "marca": "VISA",
        "numero": "4111111111111111",
        "titular": "Ana Pérez",
        "vencimiento": "12/99",
        "cvv": "123",
    }
    cbu = {
        "numero": "0170099220000067890123",
        "entidad": "Banco Ejemplo",
        "titular": "Ana Pérez",
        "cuil": "20123456789",
    }
    respuesta = client.post(
        "/api/ventas",
        json=_payload(
            medio_pago="TARJETA_CREDITO",
            tarjeta=tarjeta,
            cbu=cbu,
        ),
    )
    assert respuesta.status_code == 422
    texto = respuesta.text
    assert "4111111111111111" not in texto
    assert "0170099220000067890123" not in texto
    assert '"input"' not in texto
    assert '"ctx"' not in texto


def test_limite_de_integrantes(client: TestClient) -> None:
    integrantes = [
        {
            "nombre": f"Adherente {indice}",
            "apellido": "Pérez",
            "dni": str(40_111_000 + indice),
            "fecha_nacimiento": "2010-03-15",
            "parentesco": "Hijo/a",
        }
        for indice in range(1, 22)
    ]
    respuesta = client.post("/api/ventas", json=_payload(integrantes=integrantes))
    assert respuesta.status_code == 422
    assert "input" not in respuesta.text


def test_limite_de_body(client: TestClient) -> None:
    respuesta = client.post(
        "/api/ventas",
        content=b"{" + b" " * (256 * 1024),
        headers={"Content-Type": "application/json"},
    )
    assert respuesta.status_code == 413


def test_busqueda_maxima(client: TestClient) -> None:
    respuesta = client.get("/api/ventas", params={"q": "x" * 101})
    assert respuesta.status_code == 422
    assert "input" not in respuesta.text


def test_lock_de_auditoria(client: TestClient) -> None:
    assert api_module._AUDITORIA_LOCK.acquire(blocking=False)
    try:
        respuesta = client.post("/api/auditar")
    finally:
        api_module._AUDITORIA_LOCK.release()
    assert respuesta.status_code == 409


def test_rate_limit_politica_y_limiter() -> None:
    assert _politica("POST", "/api/auditar") == (2, 60)
    assert _politica("GET", "/api/exportar/padron") == (10, 60)
    limiter = _SlidingLimiter()
    assert limiter.permitir("prueba", 2, 60)
    assert limiter.permitir("prueba", 2, 60)
    assert not limiter.permitir("prueba", 2, 60)


def test_logs_no_incluyen_query_string(
    client: TestClient,
    caplog,
) -> None:
    caplog.set_level(logging.INFO, logger="ventas_app.access")
    client.get("/ventas", params={"q": "dato-sensible"})
    mensajes = [registro.getMessage() for registro in caplog.records]
    assert any("/ventas" in mensaje for mensaje in mensajes)
    assert all("dato-sensible" not in mensaje for mensaje in mensajes)
    assert all("?" not in mensaje for mensaje in mensajes)


def test_exportacion_maxima(
    client: TestClient,
    monkeypatch,
) -> None:
    for indice in range(2):
        respuesta = client.post(
            "/api/ventas",
            json=_payload(
                dni_titular=f"3011122{indice}",
                email=f"exportacion{indice}@example.com",
                nombre_titular=f"Persona {indice}",
            ),
        )
        assert respuesta.status_code == 201, respuesta.text
    monkeypatch.setattr(exportacion, "MAX_EXPORT_ROWS", 1)
    respuesta = client.get("/api/exportar/padron", params={"estado": "PENDIENTE"})
    assert respuesta.status_code == 422
    assert "5000" not in respuesta.text


def test_credencial_sin_onclick_inline() -> None:
    plantilla = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ventas_app"
        / "templates"
        / "credencial.html"
    )
    contenido = plantilla.read_text(encoding="utf-8")
    assert "onclick" not in contenido
    assert "js/credencial.js" in contenido
