"""Endpoints REST de ventas y auditoría."""

from __future__ import annotations

import logging
from datetime import date
from threading import Lock
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from ventas_app.auditor import ejecutar_auditoria
from ventas_app.database import get_db
from ventas_app.dependencies import require_api_roles, require_api_user
from ventas_app.models import RolUsuario, Venta
from ventas_app.security import registrar_evento_seguridad
from ventas_app.schemas import (
    AuditoriaOut,
    EventoOut,
    MetricasOut,
    PaginaVentasOut,
    VentaIn,
    VentaOut,
    VentaUpdateIn,
)
from ventas_app.services.eventos import listar_eventos
from ventas_app.services.exportacion import generar_exportacion
from ventas_app.services.metricas import calcular_metricas
from ventas_app.services.ventas import (
    AporteInvalidoError,
    DatosPagoInvalidosError,
    PlanNoDisponibleError,
    VentaNoEditableError,
    VentaNoEncontradaError,
    VentaVersionDesincronizadaError,
    actualizar_venta,
    buscar_ventas,
    crear_venta,
    obtener_venta,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["ventas"],
    dependencies=[Depends(require_api_user)],
)

SessionDep = Annotated[Session, Depends(get_db)]
_AUDITORIA_LOCK = Lock()


@router.post(
    "/auditar",
    response_model=AuditoriaOut,
    tags=["auditor"],
    dependencies=[
        Depends(require_api_roles(RolUsuario.AUDITOR, RolUsuario.ADMIN))
    ],
)
def auditar_endpoint(
    request: Request,
    db: SessionDep,
) -> dict[str, Any]:
    """Ejecuta el Agente Auditor sobre las ventas pendientes."""
    if not _AUDITORIA_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay una auditoría en curso.",
        )
    try:
        resultado = ejecutar_auditoria()
        registrar_evento_seguridad(
            db,
            tipo="AUDITORIA",
            resultado="OK",
            usuario_id=getattr(request.state.usuario, "id", None),
            ip=request.client.host if request.client else None,
            detalle=(
                f"Procesadas: {resultado.get('procesadas', 0)}; "
                f"aprobadas: {resultado.get('aprobadas', 0)}; "
                f"observadas: {resultado.get('observadas', 0)}."
            ),
        )
        db.commit()
        return resultado
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Falló la ejecución del Agente Auditor")
        registrar_evento_seguridad(
            db,
            tipo="AUDITORIA",
            resultado="FALLO",
            usuario_id=getattr(request.state.usuario, "id", None),
            ip=request.client.host if request.client else None,
            detalle="Falló la ejecución de la auditoría.",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo ejecutar la auditoría.",
        ) from exc
    finally:
        _AUDITORIA_LOCK.release()


@router.post(
    "/ventas",
    response_model=VentaOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_api_roles(RolUsuario.OPERADOR, RolUsuario.ADMIN))
    ],
)
def crear_venta_endpoint(
    request: Request,
    payload: VentaIn,
    db: SessionDep,
) -> Venta:
    """Crea una venta completa y devuelve el comprobante persistido."""
    try:
        return crear_venta(
            db,
            payload,
            actor=getattr(request.state.usuario, "username", "sistema"),
        )
    except PlanNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except AporteInvalidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get(
    "/metricas",
    response_model=MetricasOut,
    dependencies=[
        Depends(require_api_roles(RolUsuario.AUDITOR, RolUsuario.ADMIN))
    ],
)
def metricas_endpoint(
    db: SessionDep,
    desde: date | None = None,
    hasta: date | None = None,
    plan_id: int | None = None,
    estado: str | None = None,
) -> MetricasOut:
    """Devuelve las métricas ejecutivas del negocio."""
    try:
        return MetricasOut.model_validate(
            calcular_metricas(
                db,
                desde=desde,
                hasta=hasta,
                plan_id=plan_id,
                estado=estado,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get(
    "/exportar/{tipo}",
    dependencies=[Depends(require_api_roles(RolUsuario.ADMIN))],
)
def exportar_endpoint(
    request: Request,
    tipo: Literal["padron", "cobranzas"],
    db: SessionDep,
    formato: Literal["csv", "json"] = "csv",
    desde: date | None = None,
    hasta: date | None = None,
    plan_id: int | None = None,
    estado: str | None = None,
) -> Response:
    """Exporta el padrón o lote según los filtros activos."""
    try:
        contenido, media_type, nombre = generar_exportacion(
            db,
            tipo=tipo,
            formato=formato,
            desde=desde,
            hasta=hasta,
            plan_id=plan_id,
            estado=estado,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    registrar_evento_seguridad(
        db,
        tipo="EXPORTACION",
        resultado="OK",
        usuario_id=getattr(request.state.usuario, "id", None),
        ip=request.client.host if request.client else None,
        detalle=f"Exportación {tipo}/{formato}.",
    )
    db.commit()
    return Response(
        content=contenido,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
        },
    )


@router.get("/ventas", response_model=PaginaVentasOut)
def listar_ventas_endpoint(
    db: SessionDep,
    q: str | None = Query(default=None, max_length=100),
    estado: str | None = None,
    plan_id: int | None = None,
    medio_pago: str | None = None,
    regimen_afiliacion: str | None = None,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=20, ge=1, le=100),
) -> PaginaVentasOut:
    """Lista ventas con búsqueda, filtros y paginación."""
    try:
        filas, total = buscar_ventas(
            db,
            q=q,
            estado=estado,
            plan_id=plan_id,
            medio_pago=medio_pago,
            regimen_afiliacion=regimen_afiliacion,
            pagina=pagina,
            por_pagina=por_pagina,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    return PaginaVentasOut(
        items=[venta for venta, _ in filas],
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        total_paginas=total_paginas,
    )


@router.get("/ventas/{venta_id}", response_model=VentaOut)
def obtener_venta_endpoint(venta_id: int, db: SessionDep) -> Venta:
    """Devuelve el detalle de una venta existente."""
    try:
        return obtener_venta(db, venta_id)
    except VentaNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/ventas/{venta_id}/eventos",
    response_model=list[EventoOut],
)
def listar_eventos_endpoint(venta_id: int, db: SessionDep) -> list[EventoOut]:
    """Devuelve el linaje de una venta, del evento más reciente al más antiguo."""
    try:
        obtener_venta(db, venta_id)
    except VentaNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return listar_eventos(db, venta_id)


@router.put(
    "/ventas/{venta_id}",
    response_model=VentaOut,
    dependencies=[
        Depends(require_api_roles(RolUsuario.OPERADOR, RolUsuario.ADMIN))
    ],
)
def actualizar_venta_endpoint(
    request: Request,
    venta_id: int,
    payload: VentaUpdateIn,
    db: SessionDep,
) -> Venta:
    """Edita un legajo pendiente u observado y lo devuelve a auditoría."""
    try:
        return actualizar_venta(
            db,
            venta_id,
            payload,
            actor=getattr(request.state.usuario, "username", "sistema"),
        )
    except VentaNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (VentaNoEditableError, VentaVersionDesincronizadaError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PlanNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except DatosPagoInvalidosError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except AporteInvalidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
