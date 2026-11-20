"""Tests unitarios del cálculo de cotización y descuentos por medio de pago."""

from __future__ import annotations

import pytest

from ventas_app.models import MedioPago, Plan
from ventas_app.services.pricing import (
    calcular_cotizacion,
    calcular_descuento_monto,
    calcular_precio_total,
    obtener_descuento_porcentaje,
)


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


@pytest.mark.parametrize(
    ("medio_pago", "descuento_esperado"),
    [
        (MedioPago.TARJETA_CREDITO, 30),
        (MedioPago.CBU, 20),
        (MedioPago.PAGO_FACIL, 0),
        (MedioPago.COBRADOR_DOMICILIO, 0),
        ("TARJETA_CREDITO", 30),
        ("CBU", 20),
        ("PAGO_FACIL", 0),
        ("COBRADOR_DOMICILIO", 0),
    ],
)
def test_obtener_descuento_porcentaje(
    medio_pago: MedioPago | str,
    descuento_esperado: int,
) -> None:
    assert obtener_descuento_porcentaje(medio_pago) == descuento_esperado


def test_obtener_descuento_porcentaje_invalido() -> None:
    with pytest.raises(ValueError, match="no reconocido"):
        obtener_descuento_porcentaje("BITCOIN")


@pytest.mark.parametrize(
    ("subtotal", "porcentaje", "esperado"),
    [
        (45_000, 30, 13_500),
        (130_000, 20, 26_000),
        # Empate .5: half-up, igual que Math.round en el frontend.
        (100_015, 30, 30_005),
        (105_005, 30, 31_502),
        (10_000, 0, 0),
        (10_000, 100, 10_000),
    ],
)
def test_calcular_descuento_monto_half_up(
    subtotal: int,
    porcentaje: int,
    esperado: int,
) -> None:
    assert calcular_descuento_monto(subtotal, porcentaje) == esperado


@pytest.mark.parametrize(
    ("subtotal", "porcentaje"),
    [(-1, 10), (10_000, -1), (10_000, 101)],
)
def test_calcular_descuento_monto_rechaza_valores_invalidos(
    subtotal: int,
    porcentaje: int,
) -> None:
    with pytest.raises(ValueError):
        calcular_descuento_monto(subtotal, porcentaje)


@pytest.mark.parametrize(
    ("subtotal", "medio_pago", "descuento_pct", "descuento_monto", "precio_final"),
    [
        # Plan Esencial titular solo (45_000)
        (45_000, MedioPago.TARJETA_CREDITO, 30, 13_500, 31_500),
        (45_000, MedioPago.CBU, 20, 9_000, 36_000),
        (45_000, MedioPago.PAGO_FACIL, 0, 0, 45_000),
        (45_000, MedioPago.COBRADOR_DOMICILIO, 0, 0, 45_000),
        # Plan Integral + 1 adherente (130_000)
        (130_000, MedioPago.TARJETA_CREDITO, 30, 39_000, 91_000),
        (130_000, MedioPago.CBU, 20, 26_000, 104_000),
        # Redondeo entero en caso de cifras no exactas
        (105_005, MedioPago.TARJETA_CREDITO, 30, 31_502, 73_503),
        (100_015, MedioPago.TARJETA_CREDITO, 30, 30_005, 70_010),
    ],
)
def test_calcular_cotizacion(
    subtotal: int,
    medio_pago: MedioPago,
    descuento_pct: int,
    descuento_monto: int,
    precio_final: int,
) -> None:
    plan = Plan(
        nombre="Plan de Prueba",
        precio_titular=subtotal,
        precio_adherente=0,
    )
    detalle = calcular_cotizacion(plan, 0, medio_pago)
    assert detalle.subtotal_base == subtotal
    assert detalle.medio_pago == medio_pago
    assert detalle.descuento_porcentaje == descuento_pct
    assert detalle.descuento_monto == descuento_monto
    assert detalle.base_bonificada == subtotal - descuento_monto
    assert detalle.aporte_estimado == 0
    assert detalle.precio_total == precio_final


@pytest.mark.parametrize(
    ("subtotal", "medio_pago", "aporte", "esperado"),
    [
        (45_000, MedioPago.PAGO_FACIL, 0, 45_000),
        (45_000, MedioPago.PAGO_FACIL, 10_000, 35_000),
        (130_000, MedioPago.TARJETA_CREDITO, 20_000, 71_000),
        (130_000, MedioPago.CBU, 0, 104_000),
        (130_000, MedioPago.CBU, 104_000, 0),
    ],
)
def test_calcular_cotizacion_con_aporte(
    subtotal: int,
    medio_pago: MedioPago,
    aporte: int,
    esperado: int,
) -> None:
    plan = Plan(
        nombre="Plan de Prueba",
        precio_titular=subtotal,
        precio_adherente=0,
    )

    detalle = calcular_cotizacion(plan, 0, medio_pago, aporte)

    assert detalle.base_bonificada >= 0
    assert detalle.aporte_estimado == aporte
    assert detalle.precio_total == esperado


def test_calcular_cotizacion_rechaza_aporte_mayor_a_la_base() -> None:
    plan = Plan(
        nombre="Plan de Prueba",
        precio_titular=45_000,
        precio_adherente=0,
    )

    with pytest.raises(ValueError, match="superar la base"):
        calcular_cotizacion(plan, 0, MedioPago.PAGO_FACIL, 45_001)

    with pytest.raises(ValueError, match="negativo"):
        calcular_cotizacion(plan, 0, MedioPago.PAGO_FACIL, -1)
