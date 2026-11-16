"""Cálculo determinístico de la cotización de una venta."""

from __future__ import annotations

from ventas_app.models import Plan


def calcular_precio_total(plan: Plan, cantidad_adherentes: int) -> int:
    """Calcula el total en ARS usando los precios vigentes del plan.

    Args:
        plan: Plan con precios de titular y adherente.
        cantidad_adherentes: Cantidad de integrantes del grupo familiar.

    Returns:
        Precio total en pesos argentinos.

    Raises:
        ValueError: Si la cantidad de adherentes es negativa.
    """
    if cantidad_adherentes < 0:
        raise ValueError("La cantidad de adherentes no puede ser negativa.")

    return plan.precio_titular + cantidad_adherentes * plan.precio_adherente
