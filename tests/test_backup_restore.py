"""Tests de durabilidad, backups cifrados, retención y restore (F26)."""

from __future__ import annotations

import sqlite3
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ventas_app.database import (
    SessionLocal,
    engine,
    verificar_integridad_db,
)
from ventas_app.services.backup import (
    ErrorBackup,
    aplicar_retencion,
    copiar_offline,
    crear_backup,
    restaurar_backup,
    verificar_backup,
)


def _payload(plan_id: int = 1) -> dict[str, Any]:
    return {
        "nombre_titular": "Ana",
        "apellido_titular": "Pérez",
        "dni_titular": "30111222",
        "fecha_nacimiento_titular": "1990-05-20",
        "email": "ana.backup@example.com",
        "telefono": "+54 11 5555-5555",
        "calle": "Av. Corrientes",
        "altura": "1234",
        "piso_depto": "2 B",
        "localidad": "Ciudad Autónoma de Buenos Aires",
        "provincia": "Ciudad Autónoma de Buenos Aires",
        "codigo_postal": "1043",
        "plan_id": plan_id,
        "medio_pago": "PAGO_FACIL",
        "ddjj": {
            "preexistencias": False,
            "internaciones_ultimos_12m": False,
            "embarazo_actual": False,
            "medicacion_cronica": False,
            "discapacidad_declarada": False,
            "detalle": None,
            "declaracion_confirmada": True,
        },
        "integrantes": [],
    }


def _crear(client: TestClient) -> dict[str, Any]:
    respuesta = client.post("/api/ventas", json=_payload())
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_sqlite_usa_wal_durabilidad_y_foreign_keys() -> None:
    with engine.connect() as conexion:
        assert conexion.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conexion.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
        assert conexion.exec_driver_sql("PRAGMA synchronous").scalar() == 2
        assert conexion.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert verificar_integridad_db()


def test_backup_cifrado_checksum_y_restore(
    client: TestClient,
    tmp_path: Path,
) -> None:
    _crear(client)

    info = crear_backup(directorio=tmp_path)
    assert info.ruta.is_file()
    assert stat.S_IMODE(info.ruta.stat().st_mode) == 0o600
    checksum = info.ruta.with_name(f"{info.ruta.name}.sha256")
    assert checksum.is_file()
    assert verificar_backup(info.ruta)
    assert b"ana.backup@example.com" not in info.ruta.read_bytes()

    restaurada = tmp_path / "restaurada.db"
    restaurar_backup(info.ruta, restaurada)
    assert restaurada.is_file()
    with sqlite3.connect(restaurada) as conexion:
        integridad = conexion.execute("PRAGMA integrity_check").fetchone()
        assert integridad == ("ok",)
        assert conexion.execute(
            "SELECT nombre_titular FROM ventas"
        ).fetchone() == ("Ana",)
        assert conexion.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' "
            "AND name='venta_eventos_no_update'"
        ).fetchone() is not None


def test_backup_invalido_es_rechazado(tmp_path: Path) -> None:
    archivo = tmp_path / "ventas-20260101-000000-diario.db.enc"
    archivo.write_bytes(b"no-es-un-backup")
    archivo.with_name(f"{archivo.name}.sha256").write_text("0" * 64)
    assert not verificar_backup(archivo)
    with pytest.raises(ErrorBackup):
        restaurar_backup(archivo, tmp_path / "destino.db")


def test_retencion_7_4_1(tmp_path: Path) -> None:
    for indice in range(9):
        archivo = tmp_path / f"ventas-2026010{indice}-000000-diario.db.enc"
        archivo.write_bytes(b"x")
        archivo.with_name(f"{archivo.name}.sha256").write_text("x")
    for indice in range(6):
        archivo = tmp_path / f"ventas-2026010{indice}-000000-semanal.db.enc"
        archivo.write_bytes(b"x")
        archivo.with_name(f"{archivo.name}.sha256").write_text("x")
    for indice in range(3):
        archivo = tmp_path / f"ventas-2026010{indice}-000000-offline.db.enc"
        archivo.write_bytes(b"x")
        archivo.with_name(f"{archivo.name}.sha256").write_text("x")

    assert len(aplicar_retencion(tmp_path, tipo="diario")) == 2
    assert len(aplicar_retencion(tmp_path, tipo="semanal")) == 2
    assert len(aplicar_retencion(tmp_path, tipo="offline")) == 2
    assert len(list(tmp_path.glob("ventas-*-diario.db.enc"))) == 7
    assert len(list(tmp_path.glob("ventas-*-semanal.db.enc"))) == 4
    assert len(list(tmp_path.glob("ventas-*-offline.db.enc"))) == 1


def test_copia_offline_del_semanal(client: TestClient, tmp_path: Path) -> None:
    _crear(client)
    semanal = crear_backup(tipo="semanal", directorio=tmp_path)
    offline_dir = tmp_path / "offline"
    info = copiar_offline(
        directorio_semanal=tmp_path,
        directorio_offline=offline_dir,
    )

    assert info.ruta.is_file()
    assert verificar_backup(info.ruta)
    assert info.ruta.name == semanal.ruta.name.replace(
        "-semanal.db.enc",
        "-offline.db.enc",
    )
    assert len(list(offline_dir.glob("*.db.enc"))) == 1


def test_offline_conserva_una_sola_copia_semanal(tmp_path: Path) -> None:
    offline_dir = tmp_path / "offline"
    for fecha in (datetime(2026, 1, 4), datetime(2026, 1, 11)):
        semanal = crear_backup(
            tipo="semanal",
            directorio=tmp_path,
            ahora=fecha,
        )
        copia = copiar_offline(
            directorio_semanal=tmp_path,
            directorio_offline=offline_dir,
        )
        assert copia.ruta.name == semanal.ruta.name.replace(
            "-semanal.db.enc",
            "-offline.db.enc",
        )

    offline = list(offline_dir.glob("ventas-*-offline.db.enc"))
    assert len(offline) == 1
    assert offline[0].name == "ventas-20260111-000000-offline.db.enc"
    assert verificar_backup(offline[0])


def test_version_optimista_y_409(client: TestClient) -> None:
    creada = _crear(client)
    assert creada["version"] == 1
    venta_id = creada["id"]

    payload = _payload()
    payload["nombre_titular"] = "Ana Actualizada"
    payload["version"] = 1
    respuesta = client.put(f"/api/ventas/{venta_id}", json=payload)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["version"] == 2

    payload["nombre_titular"] = "Cambio obsoleto"
    payload["version"] = 1
    obsoleta = client.put(f"/api/ventas/{venta_id}", json=payload)
    assert obsoleta.status_code == 409

    with SessionLocal() as db:
        nombre = db.execute(
            text("SELECT nombre_titular FROM ventas WHERE id = :id"),
            {"id": venta_id},
        ).scalar()
    assert nombre == "Ana Actualizada"


def test_eventos_son_append_only(client: TestClient) -> None:
    creada = _crear(client)
    with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "UPDATE venta_eventos SET detalle = 'alterado' "
                    "WHERE venta_id = :id"
                ),
                {"id": creada["id"]},
            )
            db.commit()
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(
                text("DELETE FROM venta_eventos WHERE venta_id = :id"),
                {"id": creada["id"]},
            )
            db.commit()
        db.rollback()
        count = db.execute(
            text("SELECT COUNT(*) FROM venta_eventos WHERE venta_id = :id"),
            {"id": creada["id"]},
        ).scalar()
    assert count == 1
