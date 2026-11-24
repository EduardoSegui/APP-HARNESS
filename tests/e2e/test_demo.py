"""Flujo E2E de demostración (F31)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.e2e.runtime import (
    DemoCredentials,
    abrir_tablero,
    auditar,
    crear_venta,
    eliminar_venta,
    login,
    reabrir_aprobada,
)

pytestmark = pytest.mark.e2e


def test_flujo_admin_demo(
    page: Page,
    demo_base: tuple[str, DemoCredentials],
) -> None:
    base, credenciales = demo_base
    login(page, base, credenciales)
    crear_venta(page, base)
    auditar(page, base)
    abrir_tablero(page, base)
    reabrir_aprobada(page, base)
    eliminar_venta(page, base)
