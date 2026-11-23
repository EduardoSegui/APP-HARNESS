"""Tests de privacidad, cifrado de campos, MCP y LLM (F25)."""

from __future__ import annotations

import asyncio
import json
import stat
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ventas_app import config
from ventas_app.auditor import (
    ClienteMCPStdio,
    ConfiguracionLLM,
    _entorno_servidor,
    generar_resumen_llm,
)
from ventas_app.crypto import descifrar_texto
from ventas_app.database import SessionLocal, engine, init_db
from ventas_app.models import SecurityEvent, Venta
from ventas_app.services.llm import es_endpoint_local


def _payload(*, detalle: str | None = None) -> dict[str, Any]:
    return {
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
        "plan_id": 1,
        "medio_pago": "PAGO_FACIL",
        "ddjj": {
            "preexistencias": detalle is not None,
            "internaciones_ultimos_12m": False,
            "embarazo_actual": False,
            "medicacion_cronica": False,
            "discapacidad_declarada": False,
            "detalle": detalle,
            "declaracion_confirmada": True,
        },
        "integrantes": [],
    }


def _crear_venta(client: TestClient, detalle: str | None = None) -> dict[str, Any]:
    respuesta = client.post("/api/ventas", json=_payload(detalle=detalle))
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_ddjj_detalle_cifrado_en_reposo_y_legible_por_orm(
    client: TestClient,
) -> None:
    detalle = "Hipertensión controlada con medicación."
    creada = _crear_venta(client, detalle)

    with engine.connect() as conexion:
        crudo = conexion.exec_driver_sql(
            "SELECT ddjj_detalle FROM ventas WHERE id = ?",
            (creada["id"],),
        ).scalar()
    assert isinstance(crudo, str)
    assert crudo != detalle
    assert crudo.startswith("gAAAA")

    with SessionLocal() as db:
        venta = db.scalar(select(Venta).where(Venta.id == creada["id"]))
        assert venta is not None
        assert venta.ddjj_detalle == detalle

    detalle_api = client.get(f"/api/ventas/{creada['id']}")
    assert detalle_api.status_code == 200
    assert detalle_api.json()["ddjj_detalle"] == detalle


def test_detalle_con_prefijo_gAAAA_tambien_se_cifra(
    client: TestClient,
) -> None:
    detalle = "gAAAA" + ("A" * 100)
    creada = _crear_venta(client, detalle)

    with engine.connect() as conexion:
        crudo = conexion.exec_driver_sql(
            "SELECT ddjj_detalle FROM ventas WHERE id = ?",
            (creada["id"],),
        ).scalar()
    assert isinstance(crudo, str)
    assert crudo != detalle
    assert descifrar_texto(crudo) == detalle

    init_db()
    with engine.connect() as conexion:
        crudo_despues = conexion.exec_driver_sql(
            "SELECT ddjj_detalle FROM ventas WHERE id = ?",
            (creada["id"],),
        ).scalar()
    assert crudo_despues == crudo

    # Simula una fila histórica que quedó en claro con el prefijo engañoso.
    legacy = "gAAAA" + ("B" * 100)
    with engine.begin() as conexion:
        conexion.exec_driver_sql(
            "UPDATE ventas SET ddjj_detalle = ? WHERE id = ?",
            (legacy, creada["id"]),
        )
    init_db()
    with engine.connect() as conexion:
        crudo_legacy = conexion.exec_driver_sql(
            "SELECT ddjj_detalle FROM ventas WHERE id = ?",
            (creada["id"],),
        ).scalar()
    assert isinstance(crudo_legacy, str)
    assert crudo_legacy != legacy
    assert descifrar_texto(crudo_legacy) == legacy

    detalle_api = client.get(f"/api/ventas/{creada['id']}")
    assert detalle_api.status_code == 200
    assert detalle_api.json()["ddjj_detalle"] == legacy


def test_migracion_cifra_detalle_historico(client: TestClient) -> None:
    detalle = "Dato histórico que estaba en texto plano."
    creada = _crear_venta(client, detalle)

    with engine.begin() as conexion:
        conexion.exec_driver_sql(
            "UPDATE ventas SET ddjj_detalle = ? WHERE id = ?",
            (detalle, creada["id"]),
        )

    init_db()

    with engine.connect() as conexion:
        crudo = conexion.exec_driver_sql(
            "SELECT ddjj_detalle FROM ventas WHERE id = ?",
            (creada["id"],),
        ).scalar()
    assert isinstance(crudo, str)
    assert crudo != detalle
    assert crudo.startswith("gAAAA")

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.ddjj_detalle == detalle


def test_mcp_no_recibe_clave_y_no_devuelve_salud(
    client: TestClient,
) -> None:
    creada = _crear_venta(
        client,
        "Detalle de salud que no debe salir por MCP.",
    )

    async def obtener() -> dict[str, Any]:
        async with ClienteMCPStdio() as cliente:
            return await cliente.obtener_detalle(creada["id"])

    detalle = asyncio.run(obtener())

    assert detalle["ddjj_detalle"] == "[cifrado]"
    assert "Detalle de salud" not in json.dumps(detalle, ensure_ascii=False)


def test_listado_api_minimiza_salud_y_pago(client: TestClient) -> None:
    _crear_venta(client, "Condición de salud reservada.")

    respuesta = client.get("/api/ventas")
    assert respuesta.status_code == 200
    item = respuesta.json()["items"][0]

    assert item["nombre_titular"] == "Ana"
    for campo in (
        "ddjj_detalle",
        "ddjj_preexistencias",
        "cuil_titular",
        "pago_titular",
        "pago_ultimos_4",
        "pago_cuil",
        "email",
        "telefono",
        "calle",
    ):
        assert campo not in item


def test_session_storage_solo_guarda_paso_y_plan() -> None:
    fuente = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ventas_app"
        / "static"
        / "js"
        / "wizard.js"
    ).read_text(encoding="utf-8")
    inicio = fuente.index("function guardarEstado()")
    fin = fuente.index("function valorEn", inicio)
    bloque = fuente[inicio:fin]

    assert "sessionStorage.setItem" in bloque
    assert "paso: estado.paso" in bloque
    assert "plan_id: estado.plan_id" in bloque
    for campo in ("ddjj", "cuil", "medio_pago", "titular", "tarjeta", "cbu"):
        assert campo not in bloque


def test_entorno_mcp_no_hereda_secretos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-no-debe-pasar")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "clave-no-debe-pasar")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/mcp-test.db")

    entorno = _entorno_servidor()

    assert "OPENAI_API_KEY" not in entorno
    assert "OPENAI_BASE_URL" not in entorno
    assert "APP_ENCRYPTION_KEY" not in entorno
    assert entorno["VENTAS_SKIP_DOTENV"] == "1"
    assert entorno["DATABASE_URL"] == "sqlite:////tmp/mcp-test.db"
    assert entorno["PYTHONPATH"]


def test_llm_externo_solo_recibe_codigos_y_conteos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_EXTERNAL_ENABLED", "true")
    pedidos: list[httpx.Request] = []

    def responder(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Resumen agregado."}}]},
        )

    config_llm = ConfiguracionLLM(
        api_key="sk-externa",
        base_url="https://api.proveedor.example/v1",
        modelo="modelo-externo",
        timeout=1.0,
    )
    assert config_llm.externo is True

    resultado = generar_resumen_llm(
        1,
        2,
        [
            "Venta #1: R1: DNI 30111222 con salud Hipertensión.",
            "Venta #1: R2: El DNI 30111222 está repetido; email ana@example.com.",
            "Venta #2: R7: embargo / internación.",
        ],
        config=config_llm,
        transport=httpx.MockTransport(responder),
    )

    assert resultado.ok is True
    assert len(pedidos) == 1
    carga = json.loads(pedidos[0].content)
    texto = json.dumps(carga, ensure_ascii=False)
    for dato in (
        "30111222",
        "Hipertensión",
        "ana@example.com",
        "embargo",
        "internación",
    ):
        assert dato not in texto
    assert "R1: 1" in texto
    assert "R2: 1" in texto
    assert "R7: 1" in texto
    assert "1 aprobadas" in texto
    assert "2 observadas" in texto

    with SessionLocal() as db:
        evento = db.scalar(
            select(SecurityEvent).where(SecurityEvent.tipo == "LLM_EXTERNO")
        )
        assert evento is not None
        assert evento.resultado == "OK"
        assert "30111222" not in (evento.detalle or "")


def test_llm_externo_http_se_rechaza(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_EXTERNAL_ENABLED", "true")

    def no_llamar(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("No debe enviarse por HTTP externo")

    resultado = generar_resumen_llm(
        1,
        0,
        ["R1: observación."],
        config=ConfiguracionLLM(
            api_key="sk-externa",
            base_url="http://api.proveedor.example/v1",
        ),
        transport=httpx.MockTransport(no_llamar),
    )

    assert resultado.ok is False
    assert "requiere HTTPS" in (resultado.advertencia or "")


def test_llm_externo_deshabilitado_no_hace_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LLM_EXTERNAL_ENABLED", raising=False)

    def no_llamar(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("El proveedor externo no debe llamarse")

    resultado = generar_resumen_llm(
        1,
        0,
        ["R1: observación."],
        config=ConfiguracionLLM(
            api_key="sk-externa",
            base_url="https://api.proveedor.example/v1",
        ),
        transport=httpx.MockTransport(no_llamar),
    )

    assert resultado.ok is False
    assert "externo deshabilitado" in (resultado.advertencia or "")


def test_clasificacion_de_endpoint_local() -> None:
    assert es_endpoint_local("http://localhost:11434/v1")
    assert es_endpoint_local("http://127.0.0.1:11434/v1")
    assert es_endpoint_local("http://192.168.1.10:11434/v1")
    assert not es_endpoint_local("https://api.openai.com/v1")


def test_permisos_de_archivos_sensibles(client: TestClient) -> None:
    ruta_db = Path(engine.url.database or "")
    if ruta_db.exists():
        assert stat.S_IMODE(ruta_db.stat().st_mode) == 0o600
    if config.ENV_FILE.exists():
        assert stat.S_IMODE(config.ENV_FILE.stat().st_mode) == 0o600
