#!/usr/bin/env python3
"""CLI administrativa de privacidad, retención y derechos.

Requiere acceso de ADMIN/custodio al servidor. No hay endpoints web de
supresión o anonimización.
"""

from __future__ import annotations

import argparse
import sys

from ventas_app.database import SessionLocal, init_db
from ventas_app.services.privacidad import (
    ErrorPrivacidad,
    anonimizar_venta,
    asegurar_politicas_default,
    crear_legal_hold,
    crear_solicitud_derecho,
    ejecutar_retencion_seguridad,
    liberar_legal_hold,
    listar_solicitudes,
    resolver_solicitud_derecho,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Privacidad y DSR")
    parser.add_argument(
        "comando",
        choices=[
            "retencion",
            "solicitud",
            "resolver",
            "hold",
            "liberar",
            "anonimizar",
            "listar",
        ],
    )
    parser.add_argument("--venta", type=int)
    parser.add_argument(
        "--tipo",
        choices=["ACCESO", "RECTIFICACION", "SUPRESION", "ANONIMIZACION"],
    )
    parser.add_argument("--detalle")
    parser.add_argument("--actor", default="admin")
    parser.add_argument("--id", type=int, dest="solicitud_id")
    parser.add_argument("--motivo")
    parser.add_argument("--hold", type=int, dest="hold_id")
    parser.add_argument(
        "--backup",
        help="Backup cifrado verificado previo a supresión/anonimización",
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Confirmación explícita del custodio",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    init_db()
    try:
        with SessionLocal() as db:
            asegurar_politicas_default(db)
            if args.comando == "retencion":
                eliminados = ejecutar_retencion_seguridad(db)
                print(f"Eventos de seguridad eliminados: {eliminados}")
                return 0
            if args.comando == "listar":
                for solicitud in listar_solicitudes(db):
                    print(
                        f"#{solicitud.id} venta={solicitud.venta_id} "
                        f"tipo={solicitud.tipo} estado={solicitud.estado}"
                    )
                return 0
            if args.comando == "hold":
                if args.venta is None or not args.motivo:
                    raise ErrorPrivacidad("Indicá --venta y --motivo.")
                hold = crear_legal_hold(
                    db,
                    venta_id=args.venta,
                    motivo=args.motivo,
                    actor=args.actor,
                )
                print(f"Legal hold #{hold.id} activo para venta {hold.venta_id}.")
                return 0
            if args.comando == "liberar":
                if args.hold_id is None:
                    raise ErrorPrivacidad("Indicá --hold.")
                hold = liberar_legal_hold(db, args.hold_id, actor=args.actor)
                print(f"Legal hold #{hold.id} liberado.")
                return 0
            if args.comando == "solicitud":
                if args.venta is None or args.tipo is None:
                    raise ErrorPrivacidad("Indicá --venta y --tipo.")
                solicitud = crear_solicitud_derecho(
                    db,
                    venta_id=args.venta,
                    tipo=args.tipo,
                    detalle=args.detalle,
                    actor=args.actor,
                )
                print(f"Solicitud #{solicitud.id} creada ({solicitud.tipo}).")
                return 0
            if args.comando == "resolver":
                if args.solicitud_id is None:
                    raise ErrorPrivacidad("Indicá --id.")
                solicitud = resolver_solicitud_derecho(
                    db,
                    args.solicitud_id,
                    actor=args.actor,
                    archivo_backup=args.backup,
                    confirmar=args.confirmar,
                )
                print(f"Solicitud #{solicitud.id} resuelta.")
                return 0
            if args.venta is None:
                raise ErrorPrivacidad("Indicá --venta.")
            venta = anonimizar_venta(
                db,
                args.venta,
                actor=args.actor,
                archivo_backup=args.backup,
                confirmar=args.confirmar,
            )
            print(f"Venta #{venta.id} anonimizada.")
            return 0
    except ErrorPrivacidad as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
