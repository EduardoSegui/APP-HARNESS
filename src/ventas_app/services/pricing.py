"""Cálculo determinístico de la cotización de una venta y descuentos por medio de pago."""

from __future__ import annotations

from dataclasses import dataclass

from ventas_app.models import MedioPago, Plan

DESCUENTOS_MEDIO_PAGO: dict[MedioPago, int] = {
    MedioPago.TARJETA_CREDITO: 30,
    MedioPago.CBU: 20,
    MedioPago.PAGO_FACIL: 0,
    MedioPago.COBRADOR_DOMICILIO: 0,
}


@dataclass(frozen=True)
class CotizacionDetalle:
    """Detalle completo de cotización con desglose del medio de pago."""

    subtotal_base: int
    medio_pago: MedioPago
    descuento_porcentaje: int
    descuento_monto: int
    precio_total: int


def obtener_descuento_porcentaje(medio_pago: MedioPago | str) -> int:
    """Devuelve el porcentaje de descuento asignado a un medio de pago."""
    if isinstance(medio_pago, str):
        try:
            medio = MedioPago(medio_pago)
        except ValueError:
            raise ValueError(f"Medio de pago no reconocido: {medio_pago}")
    else:
        medio = medio_pago
    return DESCUENTOS_MEDIO_PAGO.get(medio, 0)


def calcular_descuento_monto(subtotal_base: int, descuento_porcentaje: int) -> int:
    """Calcula el descuento con redondeo half-up y aritmética entera.

    Se usa el mismo criterio que ``Math.round`` en el frontend para evitar
    diferencias entre la vista previa y el total persistido.
    """
    if subtotal_base < 0:
        raise ValueError("El subtotal base no puede ser negativo.")
    if not 0 <= descuento_porcentaje <= 100:
        raise ValueError("El descuento debe estar entre 0 y 100.")

    return (subtotal_base * descuento_porcentaje + 50) // 100


def calcular_precio_total(plan: Plan, cantidad_adherentes: int) -> int:
    """Calcula el total base en ARS usando los precios vigentes del plan.

    Args:
        plan: Plan con precios de titular y adherente.
        cantidad_adherentes: Cantidad de integrantes del grupo familiar.

    Returns:
        Precio total base en pesos argentinos.

    Raises:
        ValueError: Si la cantidad de adherentes es negativa.
    """
    if cantidad_adherentes < 0:
        raise ValueError("La cantidad de adherentes no puede ser negativa.")

    return plan.precio_titular + cantidad_adherentes * plan.precio_adherente


def calcular_cotizacion(
    plan: Plan,
    cantidad_adherentes: int,
    medio_pago: MedioPago | str = MedioPago.PAGO_FACIL,
) -> CotizacionDetalle:
    """Calcula la cotización completa aplicando los descuentos por medio de pago."""
    subtotal = calcular_precio_total(plan, cantidad_adherentes)
    descuento_pct = obtener_descuento_porcentaje(medio_pago)
    descuento_monto = calcular_descuento_monto(subtotal, descuento_pct)
    precio_final = subtotal - descuento_monto
    medio_enum = MedioPago(medio_pago) if isinstance(medio_pago, str) else medio_pago

    return CotizacionDetalle(
        subtotal_base=subtotal,
        medio_pago=medio_enum,
        descuento_porcentaje=descuento_pct,
        descuento_monto=descuento_monto,
        precio_total=precio_final,
    )
