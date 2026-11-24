"""Tests de administración excepcional de ventas (F30)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from ventas_app.database import SessionLocal
from ventas_app.models import RolUsuario, Venta, VentaEvento
from ventas_app.security import crear_sesion
from ventas_app.services.estados import cambiar_estado_venta
from ventas_app.services.metricas import calcular_metricas
from ventas_app.services.privacidad import crear_legal_hold
from ventas_app.services.usuarios import crear_usuario


def _payload(plan_id: int = 1) -> dict[str, Any]:
    return {
        "nombre_titular": "Ana",
        "apellido_titular": "Pérez",
        "dni_titular": "30111222",
        "fecha_nacimiento_titular": "1990-05-20",
        "email": "ana.admin@example.com",
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


def _crear(client: TestClient) -> dict[str, Any]:
    respuesta = client.post("/api/ventas", json=_payload())
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _aprobar(venta_id: int) -> None:
    with SessionLocal() as db:
        cambiar_estado_venta(db, venta_id, "APROBADA")


def _version(venta_id: int) -> int:
    with SessionLocal() as db:
        venta = db.get(Venta, venta_id)
        assert venta is not None
        return venta.version


def _login_operador(anon_client: TestClient) -> None:
    with SessionLocal() as db:
        usuario = crear_usuario(
            db,
            username="operador-admin-ventas",
            password="clave-segura-123",
            rol=RolUsuario.OPERADOR,
        )
        token, csrf, _ = crear_sesion(db, usuario, autenticada=True)
        db.commit()
    anon_client.cookies.set("vos_session", token, path="/")
    anon_client.cookies.set("vos_csrf", csrf, path="/")
    anon_client.headers["X-CSRF-Token"] = csrf


def test_reabrir_aprobada_y_reauditar(client: TestClient) -> None:
    creada = _crear(client)
    _aprobar(creada["id"])
    version = _version(creada["id"])

    respuesta = client.post(
        f"/api/ventas/{creada['id']}/reabrir",
        json={"motivo": "Corrección solicitada por el afiliado", "version": version},
    )
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["estado"] == "PENDIENTE_VERIFICACION"
    assert datos["version"] == version + 1

    with SessionLocal() as db:
        evento = db.scalar(
            select(VentaEvento)
            .where(VentaEvento.venta_id == creada["id"])
            .order_by(VentaEvento.id.desc())
        )
        assert evento is not None
        assert "Reapertura administrativa" in (evento.detalle or "")
        assert evento.actor == "admin-test"

    edicion = client.get(f"/ventas/{creada['id']}/editar")
    assert edicion.status_code == 200
    assert f'"version": {datos["version"]}' in edicion.text


def test_reabrir_exige_motivo_version_y_admin(
    anon_client: TestClient,
) -> None:
    _login_operador(anon_client)
    with SessionLocal() as db:
        # Crear una venta directa no es necesario: el endpoint debe rechazar
        # por rol antes de evaluar el estado.
        pass

    respuesta = anon_client.post(
        "/api/ventas/1/reabrir",
        json={"motivo": "Motivo válido para la operación", "version": 1},
    )
    assert respuesta.status_code == 403


def test_reabrir_venta_no_aprobada_es_409(client: TestClient) -> None:
    creada = _crear(client)
    version = _version(creada["id"])
    respuesta = client.post(
        f"/api/ventas/{creada['id']}/reabrir",
        json={"motivo": "Motivo válido para la operación", "version": version},
    )
    assert respuesta.status_code == 409


def test_reabrir_valida_motivo_y_version(client: TestClient) -> None:
    creada = _crear(client)
    _aprobar(creada["id"])
    version = _version(creada["id"])

    sin_version = client.post(
        f"/api/ventas/{creada['id']}/reabrir",
        json={"motivo": "Motivo válido para la operación"},
    )
    assert sin_version.status_code == 422

    motivo_corto = client.post(
        f"/api/ventas/{creada['id']}/reabrir",
        json={"motivo": "x", "version": version},
    )
    assert motivo_corto.status_code == 422

    obsoleta = client.post(
        f"/api/ventas/{creada['id']}/reabrir",
        json={"motivo": "Motivo válido para la operación", "version": version - 1},
    )
    assert obsoleta.status_code == 409

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "APROBADA"
        assert venta.version == version


def test_baja_logica_conserva_fila_eventos_y_excluye_listados(
    client: TestClient,
) -> None:
    creada = _crear(client)
    version = _version(creada["id"])

    respuesta = client.request(
        "DELETE",
        f"/api/ventas/{creada['id']}",
        json={"motivo": "Baja solicitada por error de carga", "version": version},
    )
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["eliminada_en"] is not None
    assert datos["version"] == version + 1

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.eliminada_en is not None
        eventos = list(
            db.scalars(
                select(VentaEvento).where(
                    VentaEvento.venta_id == creada["id"]
                )
            )
        )
        assert any("Baja lógica" in (evento.detalle or "") for evento in eventos)
        assert all(evento.actor == "admin-test" for evento in eventos[-1:])

    listado = client.get("/api/ventas")
    assert listado.status_code == 200
    assert listado.json()["total"] == 0
    assert client.get(f"/api/ventas/{creada['id']}").status_code == 404
    exportacion = client.get(
        "/api/exportar/padron",
        params={"estado": "PENDIENTE_VERIFICACION"},
    )
    assert exportacion.status_code == 200
    assert "Ana" not in exportacion.text
    assert client.get("/ventas").text.find("Baja solicitada") == -1

    with SessionLocal() as db:
        metricas = calcular_metricas(db)
    assert metricas["total_ventas"] == 0


def test_baja_bloqueada_por_legal_hold(client: TestClient) -> None:
    creada = _crear(client)
    version = _version(creada["id"])
    with SessionLocal() as db:
        crear_legal_hold(
            db,
            venta_id=creada["id"],
            motivo="Requerimiento legal",
            actor="admin-test",
        )

    respuesta = client.request(
        "DELETE",
        f"/api/ventas/{creada['id']}",
        json={"motivo": "Baja solicitada por el administrador", "version": version},
    )
    assert respuesta.status_code == 409
    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.eliminada_en is None


def test_baja_solo_admin(anon_client: TestClient) -> None:
    _login_operador(anon_client)
    respuesta = anon_client.request(
        "DELETE",
        "/api/ventas/1",
        json={"motivo": "Baja solicitada por el operador", "version": 1},
    )
    assert respuesta.status_code == 403


def test_ui_admin_muestra_acciones_y_operador_no(client: TestClient) -> None:
    creada = _crear(client)
    _aprobar(creada["id"])
    version = _version(creada["id"])

    panel = client.get("/ventas")
    assert panel.status_code == 200
    assert 'data-admin-venta="reabrir"' in panel.text
    assert 'data-admin-venta="eliminar"' in panel.text
    assert f'data-version="{version}"' in panel.text

    detalle = client.get(f"/ventas/{creada['id']}")
    assert detalle.status_code == 200
    assert 'data-admin-venta="reabrir"' in detalle.text
    assert 'data-admin-venta="eliminar"' in detalle.text


def test_ui_operador_no_ve_acciones_admin(anon_client: TestClient) -> None:
    _login_operador(anon_client)
    panel = anon_client.get("/ventas")
    assert panel.status_code == 200
    assert "data-admin-venta" not in panel.text
