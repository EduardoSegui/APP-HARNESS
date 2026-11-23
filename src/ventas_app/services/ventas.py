"""Servicios de creación y consulta de ventas."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.orm.exc import StaleDataError

from ventas_app.models import (
    EstadoVenta,
    Integrante,
    MedioPago,
    Plan,
    RegimenAfiliacion,
    TipoEventoVenta,
    Venta,
)
from ventas_app.schemas import VentaIn, VentaUpdateIn
from ventas_app.services.eventos import registrar_evento
from ventas_app.services.pricing import CotizacionDetalle, calcular_cotizacion


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


class VentaNoEditableError(ValueError):
    """La venta está aprobada y no admite edición."""

    def __init__(self, venta_id: int) -> None:
        self.venta_id = venta_id
        super().__init__(
            f"La venta {venta_id} está aprobada y no puede editarse."
        )


class DatosPagoInvalidosError(ValueError):
    """Faltan o son inválidos los datos del instrumento de pago."""


class VentaVersionDesincronizadaError(ValueError):
    """La venta cambió desde que el cliente la cargó."""

    def __init__(self, venta_id: int) -> None:
        self.venta_id = venta_id
        super().__init__(
            f"La venta {venta_id} fue modificada por otra operación. "
            "Recargá el legajo antes de editar."
        )


class AporteInvalidoError(ValueError):
    """El aporte estimado no es compatible con la base bonificada."""


def _pago_vacio() -> dict[str, str | None]:
    return {
        "pago_titular": None,
        "pago_marca_entidad": None,
        "pago_ultimos_4": None,
        "pago_vencimiento": None,
        "pago_cuil": None,
    }


def _datos_pago_enmascarados(
    datos: VentaIn | VentaUpdateIn,
) -> dict[str, str | None]:
    """Deriva solo metadatos seguros; nunca devuelve PAN, CBU completo ni CVV."""
    if datos.medio_pago is MedioPago.TARJETA_CREDITO:
        if datos.tarjeta is None:
            raise DatosPagoInvalidosError(
                "Ingresá los datos de la tarjeta para el medio de pago."
            )
        return {
            "pago_titular": datos.tarjeta.titular,
            "pago_marca_entidad": datos.tarjeta.marca.value,
            "pago_ultimos_4": datos.tarjeta.numero[-4:],
            "pago_vencimiento": datos.tarjeta.vencimiento,
            "pago_cuil": None,
        }

    if datos.medio_pago is MedioPago.CBU:
        if datos.cbu is None:
            raise DatosPagoInvalidosError(
                "Ingresá los datos del CBU para el medio de pago."
            )
        return {
            "pago_titular": datos.cbu.titular,
            "pago_marca_entidad": datos.cbu.entidad,
            "pago_ultimos_4": datos.cbu.numero[-4:],
            "pago_vencimiento": None,
            "pago_cuil": datos.cbu.cuil,
        }

    return _pago_vacio()


def _pago_desde_venta(venta: Venta) -> dict[str, str | None]:
    return {
        "pago_titular": venta.pago_titular,
        "pago_marca_entidad": venta.pago_marca_entidad,
        "pago_ultimos_4": venta.pago_ultimos_4,
        "pago_vencimiento": venta.pago_vencimiento,
        "pago_cuil": venta.pago_cuil,
    }


def _resolver_pago_actualizacion(
    datos: VentaUpdateIn,
    venta: Venta,
) -> dict[str, str | None]:
    if datos.medio_pago is MedioPago.TARJETA_CREDITO:
        if datos.tarjeta is not None:
            return _datos_pago_enmascarados(datos)
        if (
            venta.medio_pago == MedioPago.TARJETA_CREDITO.value
            and venta.pago_ultimos_4
        ):
            return _pago_desde_venta(venta)
        raise DatosPagoInvalidosError(
            "Ingresá los datos de la tarjeta: la venta no tiene un instrumento "
            "enmascarado para conservar."
        )

    if datos.medio_pago is MedioPago.CBU:
        if datos.cbu is not None:
            return _datos_pago_enmascarados(datos)
        if venta.medio_pago == MedioPago.CBU.value and venta.pago_ultimos_4:
            return _pago_desde_venta(venta)
        raise DatosPagoInvalidosError(
            "Ingresá los datos del CBU: la venta no tiene un instrumento "
            "enmascarado para conservar."
        )

    return _pago_vacio()


def _datos_salud(
    datos: VentaIn | VentaUpdateIn,
) -> dict[str, object]:
    """Persiste la DDJJ ya validada y confirmada por el cliente."""
    return {
        "ddjj_completada": True,
        "ddjj_preexistencias": datos.ddjj.preexistencias,
        "ddjj_internaciones": datos.ddjj.internaciones_ultimos_12m,
        "ddjj_embarazo": datos.ddjj.embarazo_actual,
        "ddjj_medicacion_cronica": datos.ddjj.medicacion_cronica,
        "ddjj_discapacidad": datos.ddjj.discapacidad_declarada,
        "ddjj_detalle": datos.ddjj.detalle,
    }


def _calcular_cotizacion(
    plan: Plan,
    datos: VentaIn | VentaUpdateIn,
) -> CotizacionDetalle:
    try:
        return calcular_cotizacion(
            plan,
            len(datos.integrantes),
            datos.medio_pago,
            datos.aporte_estimado,
        )
    except ValueError as exc:
        raise AporteInvalidoError(str(exc)) from exc


def _construir_integrantes(
    datos: VentaIn | VentaUpdateIn,
) -> list[Integrante]:
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

    cotizacion = _calcular_cotizacion(plan, datos)
    datos_pago = _datos_pago_enmascarados(datos)
    datos_salud = _datos_salud(datos)
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
        medio_pago=cotizacion.medio_pago.value,
        subtotal_base=cotizacion.subtotal_base,
        descuento_porcentaje=cotizacion.descuento_porcentaje,
        regimen_afiliacion=datos.regimen_afiliacion.value,
        cuil_titular=datos.cuil_titular,
        aporte_estimado=cotizacion.aporte_estimado,
        **datos_pago,
        **datos_salud,
        precio_total=cotizacion.precio_total,
        integrantes=_construir_integrantes(datos),
    )

    try:
        db.add(venta)
        db.flush()
        registrar_evento(
            db,
            venta,
            TipoEventoVenta.CREADA,
            detalle=f"Alta de venta con plan {plan.nombre}.",
            actor="operador",
            estado_nuevo=venta.estado,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return venta


def actualizar_venta(
    db: Session,
    venta_id: int,
    datos: VentaUpdateIn,
) -> Venta:
    """Reemplaza un legajo editable y lo devuelve a pendiente de auditoría."""
    venta = obtener_venta(db, venta_id)
    if venta.estado == EstadoVenta.APROBADA.value:
        raise VentaNoEditableError(venta_id)
    if datos.version is not None and datos.version != venta.version:
        raise VentaVersionDesincronizadaError(venta_id)

    estado_anterior = venta.estado
    plan = db.get(Plan, datos.plan_id)
    if plan is None or not plan.activo:
        raise PlanNoDisponibleError(datos.plan_id)

    datos_pago = _resolver_pago_actualizacion(datos, venta)
    cotizacion = _calcular_cotizacion(plan, datos)

    venta.nombre_titular = datos.nombre_titular
    venta.apellido_titular = datos.apellido_titular
    venta.dni_titular = datos.dni_titular
    venta.fecha_nacimiento_titular = datos.fecha_nacimiento_titular
    venta.email = datos.email
    venta.telefono = datos.telefono
    venta.calle = datos.calle
    venta.altura = datos.altura
    venta.piso_depto = datos.piso_depto
    venta.localidad = datos.localidad
    venta.provincia = datos.provincia
    venta.codigo_postal = datos.codigo_postal
    venta.plan = plan
    venta.medio_pago = cotizacion.medio_pago.value
    venta.subtotal_base = cotizacion.subtotal_base
    venta.descuento_porcentaje = cotizacion.descuento_porcentaje
    venta.regimen_afiliacion = datos.regimen_afiliacion.value
    venta.cuil_titular = datos.cuil_titular
    venta.aporte_estimado = cotizacion.aporte_estimado
    for campo, valor in datos_pago.items():
        setattr(venta, campo, valor)
    for campo, valor in _datos_salud(datos).items():
        setattr(venta, campo, valor)
    venta.precio_total = cotizacion.precio_total
    venta.estado = EstadoVenta.PENDIENTE_VERIFICACION.value
    venta.observaciones = None

    try:
        venta.integrantes.clear()
        db.flush()
        venta.integrantes.extend(_construir_integrantes(datos))
        registrar_evento(
            db,
            venta,
            TipoEventoVenta.EDITADA,
            detalle=(
                f"Legajo actualizado: plan {plan.nombre}, "
                f"{len(datos.integrantes)} adherentes."
            ),
            actor="operador",
            estado_anterior=estado_anterior,
            estado_nuevo=venta.estado,
        )
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise VentaVersionDesincronizadaError(venta_id) from exc
    except Exception:
        db.rollback()
        raise

    db.refresh(venta)
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


def listar_ventas_pendientes(db: Session) -> list[Venta]:
    """Lista las ventas pendientes de verificación en orden de llegada."""
    return list(
        db.scalars(
            select(Venta)
            .options(joinedload(Venta.plan))
            .where(
                Venta.estado == EstadoVenta.PENDIENTE_VERIFICACION.value
            )
            .order_by(Venta.creado_en.asc(), Venta.id.asc())
        ).all()
    )


def buscar_ventas(
    db: Session,
    *,
    q: str | None = None,
    estado: str | None = None,
    plan_id: int | None = None,
    medio_pago: str | None = None,
    regimen_afiliacion: str | None = None,
    pagina: int = 1,
    por_pagina: int = 20,
) -> tuple[list[tuple[Venta, int]], int]:
    """Busca ventas con filtros combinables y paginación.

    Devuelve las filas de la página y el total de coincidencias.
    """
    if pagina < 1:
        raise ValueError("La página debe ser mayor o igual a 1.")
    if por_pagina < 1:
        raise ValueError("El tamaño de página debe ser mayor o igual a 1.")

    filtros = []
    texto = (q or "").strip()
    if texto:
        patron = f"%{texto}%"
        filtros.append(
            or_(
                Venta.dni_titular.ilike(patron),
                Venta.nombre_titular.ilike(patron),
                Venta.apellido_titular.ilike(patron),
            )
        )

    if estado:
        try:
            filtros.append(Venta.estado == EstadoVenta(estado).value)
        except ValueError as exc:
            raise ValueError("El estado de filtro no es válido.") from exc

    if plan_id is not None:
        if plan_id <= 0:
            raise ValueError("El plan de filtro no es válido.")
        filtros.append(Venta.plan_id == plan_id)

    if medio_pago:
        try:
            filtros.append(Venta.medio_pago == MedioPago(medio_pago).value)
        except ValueError as exc:
            raise ValueError("El medio de pago de filtro no es válido.") from exc

    if regimen_afiliacion:
        try:
            filtros.append(
                Venta.regimen_afiliacion
                == RegimenAfiliacion(regimen_afiliacion).value
            )
        except ValueError as exc:
            raise ValueError("El régimen de filtro no es válido.") from exc

    total = int(
        db.scalar(
            select(func.count()).select_from(Venta).where(*filtros)
        )
        or 0
    )

    cantidad_integrantes = (
        select(func.count(Integrante.id))
        .where(Integrante.venta_id == Venta.id)
        .correlate(Venta)
        .scalar_subquery()
    )
    filas = db.execute(
        select(Venta, cantidad_integrantes.label("cantidad_integrantes"))
        .options(
            joinedload(Venta.plan),
            selectinload(Venta.integrantes),
        )
        .where(*filtros)
        .order_by(Venta.creado_en.desc(), Venta.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()

    return [(venta, int(cantidad)) for venta, cantidad in filas], total


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
