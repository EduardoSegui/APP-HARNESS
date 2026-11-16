"""Servicios de creación y consulta de ventas."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ventas_app.models import Integrante, Plan, Venta
from ventas_app.schemas import VentaIn
from ventas_app.services.pricing import calcular_precio_total


class PlanNoDisponibleError(ValueError):
    """El plan solicitado no existe o está inactivo."""

    def __init__(self, plan_id: int) -> None:
        self.plan_id = plan_id
        super().__init__(f"El plan {plan_id} no existe o no está activo.")


class VentaNoEncontradaError(LookupError):
    """No existe una venta con el identificador solicitado."""

    def __init__(self, venta_id: int) -> None:
        self.venta_id = venta_id
        super().__init__(f"La venta {venta_id} no existe.")


def _construir_integrantes(datos: VentaIn) -> list[Integrante]:
    return [
        Integrante(
            nombre=integrante.nombre,
            apellido=integrante.apellido,
            dni=integrante.dni,
            fecha_nacimiento=integrante.fecha_nacimiento,
            parentesco=integrante.parentesco.value,
        )
        for integrante in datos.integrantes
    ]


def crear_venta(db: Session, datos: VentaIn) -> Venta:
    """Crea una venta y sus integrantes en una única transacción.

    El precio total se calcula en el servidor con los precios vigentes del
    plan. El cliente no puede imponerlo.
    """
    plan = db.get(Plan, datos.plan_id)
    if plan is None or not plan.activo:
        raise PlanNoDisponibleError(datos.plan_id)

    venta = Venta(
        nombre_titular=datos.nombre_titular,
        apellido_titular=datos.apellido_titular,
        dni_titular=datos.dni_titular,
        fecha_nacimiento_titular=datos.fecha_nacimiento_titular,
        email=datos.email,
        telefono=datos.telefono,
        calle=datos.calle,
        altura=datos.altura,
        piso_depto=datos.piso_depto,
        localidad=datos.localidad,
        provincia=datos.provincia,
        codigo_postal=datos.codigo_postal,
        plan=plan,
        precio_total=calcular_precio_total(plan, len(datos.integrantes)),
        integrantes=_construir_integrantes(datos),
    )

    try:
        db.add(venta)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return venta


def obtener_venta(db: Session, venta_id: int) -> Venta:
    """Obtiene una venta con su plan e integrantes precargados."""
    venta = db.scalar(
        select(Venta)
        .options(
            joinedload(Venta.plan),
            selectinload(Venta.integrantes),
        )
        .where(Venta.id == venta_id)
    )

    if venta is None:
        raise VentaNoEncontradaError(venta_id)

    return venta


def listar_ventas(db: Session) -> list[tuple[Venta, int]]:
    """Lista las ventas de la más reciente a la más antigua.

    Cada elemento incluye la venta con su plan precargado y la cantidad de
    integrantes, calculada en la misma consulta para evitar N+1.
    """
    cantidad_integrantes = (
        select(func.count(Integrante.id))
        .where(Integrante.venta_id == Venta.id)
        .correlate(Venta)
        .scalar_subquery()
    )
    filas = db.execute(
        select(Venta, cantidad_integrantes.label("cantidad_integrantes"))
        .options(joinedload(Venta.plan))
        .order_by(Venta.creado_en.desc(), Venta.id.desc())
    ).all()

    return [(venta, int(cantidad)) for venta, cantidad in filas]
