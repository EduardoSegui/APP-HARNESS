"""Tests del sistema visual compartido de F12."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_base_carga_fuentes_css_y_shell(client: TestClient) -> None:
    html = client.get("/").text

    assert "fonts.googleapis.com" in html
    assert "Bricolage+Grotesque" in html
    assert "Public+Sans" in html
    assert "/static/css/design.css" in html
    assert 'class="app-header"' in html
    assert 'class="step-tab' in html
    assert 'id="resumen-legajo"' in html


def test_css_incluye_tokens_y_accesibilidad(client: TestClient) -> None:
    respuesta = client.get("/static/css/design.css")

    assert respuesta.status_code == 200
    assert "text/css" in respuesta.headers["content-type"]

    css = respuesta.text

    for token in ("--tinta", "--papel", "--verde", "--vino", "--mostaza"):
        assert token in css

    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css
    assert ".stamp" in css
    assert ".ledger__table" in css
