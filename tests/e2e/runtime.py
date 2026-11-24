"""Utilidades compartidas por el test E2E y el grabador de demo."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet
from playwright.sync_api import Page, expect

from ventas_app.security import _codigo_totp

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DemoCredentials:
    username: str
    password: str
    mfa_secret: str


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def construir_entorno(base: Path) -> tuple[dict[str, str], DemoCredentials]:
    """Crea un entorno aislado, con claves efímeras y datos ficticios."""
    password = "demo-admin-password-123"
    secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{base / 'demo.db'}",
            "APP_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
            "BACKUP_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
            "COOKIE_SECURE": "false",
            "ALLOWED_HOSTS": "127.0.0.1,localhost",
            "ENABLE_DOCS": "false",
            "RATE_LIMIT_ENABLED": "false",
            "VENTAS_SKIP_DOTENV": "1",
            "E2E_ADMIN_USER": "demo-admin",
            "E2E_ADMIN_PASSWORD": password,
            "E2E_ADMIN_MFA_SECRET": secret,
        }
    )
    for clave in (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "OPENAI_TIMEOUT",
        "LLM_EXTERNAL_ENABLED",
    ):
        env.pop(clave, None)
    return env, DemoCredentials("demo-admin", password, secret)


def preparar_base(env: dict[str, str]) -> None:
    subprocess.run(
        [sys.executable, "-m", "tests.e2e.seed"],
        cwd=ROOT,
        env=env,
        check=True,
    )


def iniciar_servidor(env: dict[str, str]) -> tuple[subprocess.Popen, str]:
    puerto = _puerto_libre()
    proceso = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ventas_app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(puerto),
            "--no-access-log",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    base = f"http://127.0.0.1:{puerto}"
    limite = time.monotonic() + 30
    while time.monotonic() < limite:
        if proceso.poll() is not None:
            error = proceso.stderr.read() if proceso.stderr else ""
            raise RuntimeError(f"El servidor E2E terminó: {error}")
        try:
            respuesta = httpx.get(f"{base}/health", timeout=1)
            if respuesta.status_code == 200:
                return proceso, base
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    proceso.terminate()
    raise RuntimeError("El servidor E2E no inició a tiempo.")


def detener_servidor(proceso: subprocess.Popen) -> None:
    proceso.terminate()
    try:
        proceso.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proceso.kill()
        proceso.wait(timeout=5)


def login(page: Page, base: str, credenciales: DemoCredentials) -> None:
    page.goto(f"{base}/login")
    page.locator("#login-username").fill(credenciales.username)
    page.locator("#login-password").fill(credenciales.password)
    page.get_by_role("button", name="Ingresar").click()
    expect(page).to_have_url(re.compile(rf"{re.escape(base)}/mfa"))
    page.locator("#mfa-codigo").fill(
        _codigo_totp(
            credenciales.mfa_secret,
            int(time.time()) // 30,
        )
    )
    page.get_by_role("button", name="Confirmar").click()
    expect(page).to_have_url(f"{base}/")
    expect(page.locator("#wizard")).to_be_visible()


def crear_venta(page: Page, base: str) -> None:
    page.goto(f"{base}/")
    page.locator("#titular-nombre").fill("Demo")
    page.locator("#titular-apellido").fill("Afiliado")
    page.locator("#titular-dni").fill("30111222")
    page.locator("#titular-fecha-nacimiento").fill("1990-05-20")
    page.locator("#titular-email").fill("demo.afiliado@example.test")
    page.locator("#titular-telefono").fill("1145678901")
    for nombre in (
        "ddjj-preexistencias",
        "ddjj-internaciones",
        "ddjj-embarazo",
        "ddjj-medicacion",
        "ddjj-discapacidad",
    ):
        page.locator(f'input[name="{nombre}"][value="no"]').check()
    page.locator("#ddjj-confirmada").check()
    page.locator("#btn-siguiente-1").click()
    expect(page.locator('[data-paso="2"]')).to_be_visible()

    page.locator("#domicilio-calle").fill("Av. Demo")
    page.locator("#domicilio-altura").fill("123")
    page.locator("#domicilio-localidad").fill("Ciudad Demo")
    page.locator("#domicilio-provincia").select_option(
        "Ciudad Autónoma de Buenos Aires"
    )
    page.locator("#domicilio-codigo-postal").fill("1043")
    page.locator("#btn-siguiente-2").click()
    expect(page.locator('[data-paso="3"]')).to_be_visible()

    page.locator('input[name="plan_id"]').first.check(force=True)
    page.locator('input[name="medio_pago"][value="PAGO_FACIL"]').check(
        force=True
    )
    page.locator("#privacidad-aceptada").check()
    page.locator("#btn-confirmar").click()
    expect(page.locator("#comprobante")).to_be_visible(timeout=15000)


def auditar(page: Page, base: str) -> None:
    page.goto(f"{base}/ventas")
    page.locator("#btn-auditar").click()
    expect(page.locator("#auditoria-estado")).to_contain_text(
        "Auditoría finalizada",
        timeout=60000,
    )
    expect(page.locator("#panel-auditoria")).to_be_visible()


def abrir_tablero(page: Page, base: str) -> None:
    page.goto(f"{base}/dashboard")
    expect(page.locator("h1")).to_contain_text("Gestión del padrón")


def reabrir_aprobada(page: Page, base: str) -> None:
    page.goto(f"{base}/ventas")
    page.get_by_role("button", name="Reabrir").first.click()
    expect(page.locator("#admin-venta-dialog")).to_be_visible()
    page.locator("#admin-venta-motivo").fill(
        "Corrección solicitada para la demo ficticia"
    )
    page.locator("#admin-venta-confirmar").click()
    expect(page).to_have_url(
        re.compile(rf"{re.escape(base)}/ventas/\d+/editar"),
        timeout=15000,
    )


def eliminar_venta(page: Page, base: str) -> None:
    page.goto(f"{base}/ventas")
    page.get_by_role("button", name="Eliminar").first.click()
    expect(page.locator("#admin-venta-dialog")).to_be_visible()
    page.locator("#admin-venta-motivo").fill(
        "Baja solicitada para la demo ficticia"
    )
    page.locator("#admin-venta-confirmar").click()
    expect(page).to_have_url(f"{base}/ventas", timeout=15000)
    expect(page.locator("[data-admin-venta='eliminar']")).to_have_count(0)


def flujo_demo(
    page: Page,
    base: str,
    credenciales: DemoCredentials,
    *,
    pausa_ms: int = 0,
) -> None:
    login(page, base, credenciales)
    if pausa_ms:
        page.wait_for_timeout(pausa_ms)
    crear_venta(page, base)
    if pausa_ms:
        page.wait_for_timeout(pausa_ms)
    auditar(page, base)
    if pausa_ms:
        page.wait_for_timeout(pausa_ms)
    abrir_tablero(page, base)
    if pausa_ms:
        page.wait_for_timeout(pausa_ms)
    reabrir_aprobada(page, base)
    if pausa_ms:
        page.wait_for_timeout(pausa_ms)
    eliminar_venta(page, base)


def url_valida(base: str) -> bool:
    parsed = urlparse(base)
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}


__all__ = [
    "DemoCredentials",
    "abrir_tablero",
    "auditar",
    "construir_entorno",
    "crear_venta",
    "detener_servidor",
    "eliminar_venta",
    "flujo_demo",
    "iniciar_servidor",
    "login",
    "preparar_base",
    "reabrir_aprobada",
]
