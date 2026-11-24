"""Fixtures de navegador y servidor aislado para E2E (F31)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from tests.e2e.runtime import (
    DemoCredentials,
    construir_entorno,
    detener_servidor,
    iniciar_servidor,
    preparar_base,
)


@pytest.fixture(scope="session")
def demo_base(tmp_path_factory) -> Iterator[tuple[str, DemoCredentials]]:
    base_dir = tmp_path_factory.mktemp("f31-demo")
    env, credenciales = construir_entorno(base_dir)
    preparar_base(env)
    proceso, base = iniciar_servidor(env)
    try:
        yield base, credenciales
    finally:
        detener_servidor(proceso)


@pytest.fixture
def playwright_instance() -> Iterator[Playwright]:
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture
def browser(playwright_instance: Playwright) -> Iterator[Browser]:
    try:
        navegador = playwright_instance.chromium.launch(
            channel="chrome",
            headless=True,
        )
    except Exception:
        navegador = playwright_instance.chromium.launch(headless=True)
    try:
        yield navegador
    finally:
        navegador.close()


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    contexto = browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="es-AR",
    )
    pagina = contexto.new_page()
    try:
        yield pagina
    finally:
        contexto.close()
