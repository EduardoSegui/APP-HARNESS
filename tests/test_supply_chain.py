"""Tests de cadena de suministro y assets self-hosted (F28)."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "ventas_app" / "static"


def _hashes() -> dict[str, str]:
    resultado: dict[str, str] = {}
    for linea in (STATIC / "ASSETS.lock").read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        ruta, digest = linea.split()
        resultado[ruta] = digest
    return resultado


def test_assets_lock_coincide_con_archivos() -> None:
    hashes = _hashes()
    assert "vendor/tailwindcss-3.4.17.js" in hashes
    assert len(hashes) == 7
    for ruta, esperado in hashes.items():
        archivo = STATIC / ruta
        assert archivo.is_file(), ruta
        real = hashlib.sha256(archivo.read_bytes()).hexdigest()
        assert real == esperado, ruta


def test_no_hay_cdn_externo_en_html_ni_csp(client: TestClient) -> None:
    html = client.get("/").text
    csp = client.get("/health").headers["content-security-policy"]

    for externo in ("cdn.tailwindcss.com", "fonts.googleapis.com", "fonts.gstatic.com"):
        assert externo not in html
        assert externo not in csp
    assert "/static/vendor/tailwindcss-3.4.17.js" in html
    assert "script-src 'self'" in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp


def test_assets_self_hosted_se_sirven(client: TestClient) -> None:
    for ruta in (
        "/static/vendor/tailwindcss-3.4.17.js",
        "/static/fonts/font-1.ttf",
        "/static/fonts/font-6.ttf",
        "/static/ASSETS.lock",
    ):
        respuesta = client.get(ruta)
        assert respuesta.status_code == 200, ruta


def test_uv_lock_esta_actualizado() -> None:
    resultado = subprocess.run(
        ["uv", "lock", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr


def test_escaneo_local_basico_no_encuentra_secretos() -> None:
    # Complemento local de gitleaks; el CI ejecuta gitleaks sobre el repo.
    patrones = (
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    )
    candidatos = [
        ROOT / "src",
        ROOT / "scripts",
        ROOT / "tests",
    ]
    for base in candidatos:
        for archivo in base.rglob("*"):
            if not archivo.is_file() or "__pycache__" in archivo.parts:
                continue
            try:
                texto = archivo.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for patron in patrones:
                assert not patron.search(texto), f"posible secreto en {archivo}"
