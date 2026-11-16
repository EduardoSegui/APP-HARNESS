"""Tests unitarios del cálculo de cotización."""

from __future__ import annotations

import pytest

from ventas_app.models import Plan
from ventas_app.services.pricing import calcular_precio_total


@pytest.mark.parametrize(
    ("precio_titular", "precio_adherente", "cantidad", "esperado"),
    [
        (45_000, 30_000, 0, 45_000),
        (45_000, 30_000, 2, 105_000),
        (78_000, 52_000, 1, 130_000),
        (78_000, 52_000, 2, 182_000),
        (125_000, 85_000, 3, 380_000),
    ],
)
def test_calcular_precio_total(
    precio_titular: int,
    precio_adherente: int,
    cantidad: int,
    esperado: int,
) -> None:
    plan = Plan(
        nombre="Plan de Prueba",
        precio_titular=precio_titular,
        precio_adherente=precio_adherente,
    )

    assert calcular_precio_total(plan, cantidad) == esperado


def test_calcular_precio_total_rechaza_cantidad_negativa() -> None:
    plan = Plan(
        nombre="Plan de Prueba",
        precio_titular=45_000,
        precio_adherente=30_000,
    )

    with pytest.raises(ValueError, match="no puede ser negativa"):
        calcular_precio_total(plan, -1)
