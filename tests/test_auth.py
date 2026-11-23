"""Tests de autenticación, MFA, CSRF y RBAC (F23)."""

from __future__ import annotations

import re
import time
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from ventas_app.database import SessionLocal
from ventas_app.models import RolUsuario, Usuario
from ventas_app.security import (
    _codigo_totp,
    hash_password,
    login_rate_limiter,
    verify_password,
)
from ventas_app.services.usuarios import crear_usuario


def _crear_usuario(
    username: str,
    role: RolUsuario,
    password: str = "clave-segura-123",
) -> None:
    with SessionLocal() as db:
        crear_usuario(
            db,
            username=username,
            password=password,
            rol=role,
        )


def _csrf_de_login(html: str) -> str:
    coincidencia = re.search(
        r'name="csrf_token" value="([^"]+)"',
        html,
    )
    assert coincidencia is not None
    return coincidencia.group(1)


def _login(
    client: TestClient,
    username: str,
    password: str = "clave-segura-123",
    *,
    follow_redirects: bool = False,
):
    page = client.get("/login")
    csrf = _csrf_de_login(page.text)
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "csrf_token": csrf,
            "next": "/",
        },
        follow_redirects=follow_redirects,
    )


def _completar_mfa(client: TestClient) -> None:
    page = client.get("/mfa")
    assert page.status_code == 200
    secreto = re.search(
        r"<code>([A-Z2-7]+)</code>",
        page.text,
    )
    assert secreto is not None
    codigo = _codigo_totp(
        secreto.group(1),
        int(time.time()) // 30,
    )
    csrf = client.cookies.get("vos_csrf")
    respuesta = client.post(
        "/mfa",
        data={"codigo": codigo, "csrf_token": csrf, "next": "/"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303, respuesta.text


def test_rutas_privadas_sin_sesion(anon_client: TestClient) -> None:
    html = anon_client.get("/", follow_redirects=False)
    assert html.status_code == 303
    assert html.headers["location"].startswith("/login")

    api = anon_client.get("/api/ventas")
    assert api.status_code == 401


def test_login_csrf_obligatorio(anon_client: TestClient) -> None:
    respuesta = anon_client.post(
        "/login",
        data={"username": "x", "password": "clave-segura-123"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 403


def test_password_argon2_y_login_operador(anon_client: TestClient) -> None:
    _crear_usuario("operador1", RolUsuario.OPERADOR)
    with SessionLocal() as db:
        usuario = db.scalar(
            select(Usuario).where(Usuario.username == "operador1")
        )
        assert usuario is not None
        assert usuario.password_hash != "clave-segura-123"
        assert verify_password(usuario.password_hash, "clave-segura-123")

    respuesta = _login(anon_client, "operador1")
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/"
    assert anon_client.get("/").status_code == 200
    assert anon_client.get("/dashboard").status_code == 403
    assert anon_client.get("/api/exportar/padron").status_code == 403


def test_mfa_admin_setup_y_acceso(anon_client: TestClient) -> None:
    _crear_usuario("admin1", RolUsuario.ADMIN)
    respuesta = _login(anon_client, "admin1")
    assert respuesta.status_code == 303
    assert "/mfa" in respuesta.headers["location"]

    _completar_mfa(anon_client)

    assert anon_client.get("/").status_code == 200
    assert anon_client.get("/dashboard").status_code == 200
    assert anon_client.get("/api/exportar/padron?formato=json").status_code == 200


def test_rbac_auditor_y_operador(anon_client: TestClient) -> None:
    _crear_usuario("auditor1", RolUsuario.AUDITOR)
    assert _login(anon_client, "auditor1").status_code == 303
    _completar_mfa(anon_client)
    assert anon_client.get("/dashboard").status_code == 200
    assert anon_client.get("/").status_code == 403
    assert anon_client.post("/api/ventas", json={}).status_code == 403

    anon_client.cookies.clear()
    _crear_usuario("operador2", RolUsuario.OPERADOR)
    assert _login(anon_client, "operador2").status_code == 303
    assert anon_client.get("/ventas").status_code == 200
    assert anon_client.get("/dashboard").status_code == 403


def test_csrf_api_obligatorio(client: TestClient) -> None:
    headers = client.headers.pop("X-CSRF-Token")
    try:
        respuesta = client.post(
            "/api/ventas",
            json={
                "nombre_titular": "Ana",
                "apellido_titular": "Pérez",
                "dni_titular": "30111222",
                "fecha_nacimiento_titular": "1990-05-20",
                "email": "ana@example.com",
                "telefono": "1145678901",
                "calle": "Av. Corrientes",
                "altura": "1234",
                "piso_depto": None,
                "localidad": "CABA",
                "provincia": "Ciudad Autónoma de Buenos Aires",
                "codigo_postal": "1043",
                "plan_id": 1,
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
        assert respuesta.status_code == 403
    finally:
        client.headers["X-CSRF-Token"] = headers


def test_login_rate_limit(anon_client: TestClient) -> None:
    _crear_usuario("operador-rate", RolUsuario.OPERADOR)
    login_rate_limiter.limpiar()
    page = anon_client.get("/login")
    csrf = _csrf_de_login(page.text)
    for _ in range(6):
        respuesta = anon_client.post(
            "/login",
            data={
                "username": "operador-rate",
                "password": "incorrecta-123",
                "csrf_token": csrf,
                "next": "/",
            },
            follow_redirects=False,
        )
    assert respuesta.status_code == 429
