"""Tests de privacidad, retención, legal hold, DSR y consentimiento (F27)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ventas_app.database import SessionLocal
from ventas_app.models import (
    ConsentimientoPrivacidad,
    RetencionPolitica,
    RolUsuario,
    SecurityEvent,
    SolicitudDerecho,
    Venta,
)
from ventas_app.security import crear_sesion
from ventas_app.services.backup import crear_backup
from ventas_app.services.privacidad import (
    ErrorPrivacidad,
    anonimizar_venta,
    asegurar_politicas_default,
    crear_legal_hold,
    crear_solicitud_derecho,
    ejecutar_retencion_seguridad,
    liberar_legal_hold,
    resolver_solicitud_derecho,
)
from ventas_app.services.usuarios import crear_usuario


def _payload(*, consentimiento: bool = False) -> dict[str, Any]:
    return {
        "nombre_titular": "Ana",
        "apellido_titular": "Pérez",
        "dni_titular": "30111222",
        "fecha_nacimiento_titular": "1990-05-20",
        "email": "ana.privacidad@example.com",
        "telefono": "+54 11 5555-5555",
        "calle": "Av. Corrientes",
        "altura": "1234",
        "piso_depto": "2 B",
        "localidad": "Ciudad Autónoma de Buenos Aires",
        "provincia": "Ciudad Autónoma de Buenos Aires",
        "codigo_postal": "1043",
        "plan_id": 1,
        "medio_pago": "PAGO_FACIL",
        "consentimiento_privacidad": consentimiento,
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


def _crear(client: TestClient, *, consentimiento: bool = False) -> dict[str, Any]:
    respuesta = client.post(
        "/api/ventas",
        json=_payload(consentimiento=consentimiento),
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_aviso_privacidad_publico_y_versionado(client: TestClient) -> None:
    respuesta = client.get("/privacidad")
    assert respuesta.status_code == 200
    assert "Aviso de privacidad" in respuesta.text
    assert "2026-11-23" in respuesta.text
    assert "Ley 25.326" in respuesta.text


def test_wizard_muestra_aviso_y_consentimiento(client: TestClient) -> None:
    html = client.get("/").text
    assert 'id="privacidad-aceptada"' in html
    assert "aviso de privacidad" in html
    assert 'href="/privacidad"' in html


def test_consentimiento_se_registra_al_crear(client: TestClient) -> None:
    venta = _crear(client, consentimiento=True)
    with SessionLocal() as db:
        consentimiento = db.scalar(
            select(ConsentimientoPrivacidad).where(
                ConsentimientoPrivacidad.venta_id == venta["id"]
            )
        )
    assert consentimiento is not None
    assert consentimiento.version == "2026-11-23"


def test_politicas_default_y_retencion_solo_seguridad(
    client: TestClient,
    db,
) -> None:
    _crear(client)
    asegurar_politicas_default(db)
    politicas = {
        p.categoria: p
        for p in db.scalars(select(RetencionPolitica)).all()
    }
    assert politicas["SEGURIDAD"].dias == 365
    assert politicas["COMERCIAL"].dias is None
    assert politicas["SALUD"].dias is None

    viejo = SecurityEvent(
        tipo="LOGIN",
        resultado="FALLO",
        creado_en=datetime.now() - timedelta(days=400),
    )
    reciente = SecurityEvent(
        tipo="LOGIN",
        resultado="OK",
        creado_en=datetime.now() - timedelta(days=1),
    )
    db.add_all([viejo, reciente])
    db.commit()

    eliminados = ejecutar_retencion_seguridad(db)
    assert eliminados >= 1
    with SessionLocal() as check:
        tipos = [e.tipo for e in check.scalars(select(SecurityEvent)).all()]
        assert "RETENCION_SEGURIDAD" in tipos
        assert check.scalar(select(Venta.id)) is not None


def test_legal_hold_bloquea_anonimizacion_y_dsr(
    client: TestClient,
    tmp_path,
) -> None:
    venta = _crear(client)
    with SessionLocal() as db:
        hold = crear_legal_hold(
            db,
            venta_id=venta["id"],
            motivo="Requerimiento legal",
            actor="admin",
        )
        with pytest.raises(ErrorPrivacidad):
            anonimizar_venta(db, venta["id"], actor="admin")
        solicitud = crear_solicitud_derecho(
            db,
            venta_id=venta["id"],
            tipo="SUPRESION",
            detalle=None,
            actor="admin",
        )
        with pytest.raises(ErrorPrivacidad):
            resolver_solicitud_derecho(db, solicitud.id, actor="admin")
        liberar_legal_hold(db, hold.id, actor="admin")

        with pytest.raises(ErrorPrivacidad):
            resolver_solicitud_derecho(db, solicitud.id, actor="admin")
        backup = crear_backup(directorio=tmp_path)
        resuelta = resolver_solicitud_derecho(
            db,
            solicitud.id,
            actor="admin",
            archivo_backup=backup.ruta,
            confirmar=True,
        )
        assert resuelta.estado == "RESUELTA"

    with SessionLocal() as db:
        anonimizada = db.get(Venta, venta["id"])
        assert anonimizada is not None
        assert anonimizada.nombre_titular == "ANONIMIZADO"
        assert anonimizada.fecha_nacimiento_titular.year == 1900
        assert anonimizada.ddjj_detalle is None
        assert anonimizada.email == "anonimizado@invalid.local"


def test_anonimizacion_exige_backup_y_confirmacion(
    client: TestClient,
    tmp_path,
) -> None:
    venta = _crear(client)
    with SessionLocal() as db:
        with pytest.raises(ErrorPrivacidad):
            anonimizar_venta(db, venta["id"], actor="admin")
        with pytest.raises(ErrorPrivacidad):
            anonimizar_venta(
                db,
                venta["id"],
                actor="admin",
                confirmar=True,
            )
        backup = crear_backup(directorio=tmp_path)
        anonimizada = anonimizar_venta(
            db,
            venta["id"],
            actor="admin",
            archivo_backup=backup.ruta,
            confirmar=True,
        )
        assert anonimizada.fecha_nacimiento_titular.year == 1900
        assert anonimizada.dni_titular == "00000000"


def test_dsr_acceso_y_rectificacion_quedan_auditados(
    client: TestClient,
) -> None:
    venta = _crear(client)
    with SessionLocal() as db:
        acceso = crear_solicitud_derecho(
            db,
            venta_id=venta["id"],
            tipo="ACCESO",
            detalle="Solicitud de acceso",
            actor="admin",
        )
        resuelta = resolver_solicitud_derecho(db, acceso.id, actor="admin")
        assert resuelta.estado == "RESUELTA"
        rectificacion = crear_solicitud_derecho(
            db,
            venta_id=venta["id"],
            tipo="RECTIFICACION",
            detalle=None,
            actor="admin",
        )
        assert rectificacion.estado == "PENDIENTE"
        eventos = db.scalars(
            select(SecurityEvent).where(SecurityEvent.tipo == "DSR")
        ).all()
    assert len(eventos) >= 2


def test_exportacion_y_denegacion_generan_eventos_sin_pii(
    client: TestClient,
) -> None:
    _crear(client)
    respuesta = client.get(
        "/api/exportar/padron",
        params={"estado": "PENDIENTE_VERIFICACION"},
    )
    assert respuesta.status_code == 200

    with SessionLocal() as db:
        evento = db.scalar(
            select(SecurityEvent).where(SecurityEvent.tipo == "EXPORTACION")
        )
    assert evento is not None
    assert "Ana" not in (evento.detalle or "")
    assert "30111222" not in (evento.detalle or "")


def test_denegacion_redirige_y_registra_evento(anon_client: TestClient) -> None:
    with SessionLocal() as db:
        usuario = crear_usuario(
            db,
            username="operador-privacidad",
            password="clave-segura-123",
            rol=RolUsuario.OPERADOR,
        )
        token, csrf, _ = crear_sesion(db, usuario, autenticada=True)
        db.commit()
        usuario_id = usuario.id
    anon_client.cookies.set("vos_session", token, path="/")
    anon_client.cookies.set("vos_csrf", csrf, path="/")

    respuesta = anon_client.get("/dashboard")
    assert respuesta.status_code == 403
    with SessionLocal() as db:
        evento = db.scalar(
            select(SecurityEvent).where(
                SecurityEvent.tipo == "ACCESO_DENEGADO",
                SecurityEvent.usuario_id == usuario_id,
            )
        )
    assert evento is not None
    assert "operador-privacidad" not in (evento.detalle or "")
