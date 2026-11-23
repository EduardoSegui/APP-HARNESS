"""Backups cifrados, verificación, restauración y retención."""

from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ventas_app.config import (
    BACKUP_ENCRYPTION_KEY,
    BACKUP_RETENTION_DAILY,
    BACKUP_RETENTION_OFFLINE,
    BACKUP_RETENTION_WEEKLY,
)
from ventas_app.crypto import cifrar_bytes, descifrar_bytes


class ErrorBackup(RuntimeError):
    """Error de creación, verificación o restauración de un backup."""


@dataclass(frozen=True, slots=True)
class BackupInfo:
    """Metadatos de un backup creado o verificado."""

    ruta: Path
    checksum: str
    bytes: int


_TIPOS = frozenset({"diario", "semanal", "offline"})
_TABLAS_MINIMAS = frozenset({"planes", "ventas", "venta_eventos"})


def _ruta_fuente(fuente: str | Path | None = None) -> Path:
    if fuente is not None:
        return Path(fuente).expanduser()
    from ventas_app.database import engine

    ruta = engine.url.database
    if not ruta or ruta == ":memory:":
        raise ErrorBackup("La base actual no es un archivo SQLite.")
    return Path(ruta).expanduser()


def _ruta_checksum(ruta: Path) -> Path:
    return ruta.with_name(f"{ruta.name}.sha256")


def _clave_backup() -> str:
    if not BACKUP_ENCRYPTION_KEY:
        raise ErrorBackup(
            "Falta BACKUP_ENCRYPTION_KEY (o APP_ENCRYPTION_KEY) para cifrar."
        )
    return BACKUP_ENCRYPTION_KEY


def _checksum(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _escribir_privado(ruta: Path, datos: bytes) -> None:
    ruta.write_bytes(datos)
    try:
        ruta.chmod(0o600)
    except OSError:
        pass


def _verificar_sqlite(ruta: Path) -> bool:
    try:
        with sqlite3.connect(f"file:{ruta}?mode=ro", uri=True) as conexion:
            integridad = conexion.execute("PRAGMA integrity_check").fetchone()
            claves = conexion.execute("PRAGMA foreign_key_check").fetchall()
            tablas = {
                fila[0]
                for fila in conexion.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
    except (sqlite3.Error, OSError):
        return False
    return (
        bool(integridad)
        and integridad[0] == "ok"
        and not claves
        and _TABLAS_MINIMAS.issubset(tablas)
    )


def verificar_backup(ruta: str | Path) -> bool:
    """Verifica checksum, descifrado e integridad de un backup."""
    archivo = Path(ruta)
    checksum_archivo = _ruta_checksum(archivo)
    if not archivo.is_file() or not checksum_archivo.is_file():
        return False
    try:
        cifrado = archivo.read_bytes()
        checksum_esperado = checksum_archivo.read_text(encoding="ascii").strip()
        if not checksum_esperado or not hmac.compare_digest(
            checksum_esperado,
            _checksum(cifrado),
        ):
            return False
        plano = descifrar_bytes(cifrado, _clave_backup())
    except (OSError, ValueError):
        return False

    with tempfile.TemporaryDirectory(prefix="ventas-backup-check-") as tmp:
        copia = Path(tmp) / "verificacion.db"
        _escribir_privado(copia, plano)
        return _verificar_sqlite(copia)


def crear_backup(
    *,
    tipo: str = "diario",
    directorio: str | Path | None = None,
    fuente: str | Path | None = None,
    ahora: datetime | None = None,
) -> BackupInfo:
    """Crea un backup consistente, cifrado y con checksum."""
    if tipo not in _TIPOS:
        raise ErrorBackup(f"Tipo de backup inválido: {tipo!r}.")
    origen = _ruta_fuente(fuente)
    if not origen.is_file():
        raise ErrorBackup(f"No existe la base a respaldar: {origen}")

    if directorio is None:
        from ventas_app.config import BACKUP_DIR

        directorio = BACKUP_DIR
    destino_dir = Path(directorio).expanduser()
    destino_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        destino_dir.chmod(0o700)
    except OSError:
        pass

    momento = ahora or datetime.now()
    nombre = f"ventas-{momento:%Y%m%d-%H%M%S}-{tipo}.db.enc"
    destino = destino_dir / nombre
    if destino.exists():
        raise ErrorBackup(f"El backup ya existe: {destino}")

    with tempfile.TemporaryDirectory(prefix="ventas-backup-") as tmp:
        copia = Path(tmp) / "origen.db"
        try:
            with sqlite3.connect(str(origen)) as origen_sql:
                with sqlite3.connect(str(copia)) as copia_sql:
                    origen_sql.backup(copia_sql)
            plano = copia.read_bytes()
        except sqlite3.Error as exc:
            raise ErrorBackup(f"No se pudo copiar la base SQLite: {exc}") from exc

    cifrado = cifrar_bytes(plano, _clave_backup())
    _escribir_privado(destino, cifrado)
    checksum = _checksum(cifrado)
    _escribir_privado(
        _ruta_checksum(destino),
        (checksum + "\n").encode("ascii"),
    )
    if not verificar_backup(destino):
        destino.unlink(missing_ok=True)
        _ruta_checksum(destino).unlink(missing_ok=True)
        raise ErrorBackup("El backup creado no pasó la verificación.")
    return BackupInfo(ruta=destino, checksum=checksum, bytes=len(cifrado))


def restaurar_backup(
    archivo: str | Path,
    destino: str | Path,
    *,
    crear_copia_previa: bool = True,
) -> Path:
    """Restaura un backup verificado en un archivo SQLite destino.

    Debe ejecutarse en modo mantenimiento y solo por ADMIN/custodio. No hay
    endpoint web de restauración.
    """
    origen = Path(archivo)
    if not verificar_backup(origen):
        raise ErrorBackup("El backup no es válido o está corrupto.")
    destino_path = Path(destino).expanduser()
    destino_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if crear_copia_previa and destino_path.exists():
        copia_previa = destino_path.with_name(
            f"{destino_path.name}.pre-restore-{datetime.now():%Y%m%d%H%M%S}"
        )
        shutil.copy2(destino_path, copia_previa)
        try:
            copia_previa.chmod(0o600)
        except OSError:
            pass

    cifrado = origen.read_bytes()
    plano = descifrar_bytes(cifrado, _clave_backup())
    with tempfile.TemporaryDirectory(prefix="ventas-restore-") as tmp:
        fuente = Path(tmp) / "restore.db"
        _escribir_privado(fuente, plano)
        if not _verificar_sqlite(fuente):
            raise ErrorBackup("El contenido descifrado no es una base válida.")
        try:
            with sqlite3.connect(str(fuente)) as fuente_sql:
                with sqlite3.connect(str(destino_path)) as destino_sql:
                    fuente_sql.backup(destino_sql)
        except sqlite3.Error as exc:
            raise ErrorBackup(f"No se pudo restaurar la base: {exc}") from exc

    try:
        destino_path.chmod(0o600)
    except OSError:
        pass
    if not _verificar_sqlite(destino_path):
        raise ErrorBackup("La base restaurada no pasó integrity_check.")
    return destino_path


def _archivos_backup(directorio: Path, tipo: str) -> list[Path]:
    return sorted(
        directorio.glob(f"ventas-*-{tipo}.db.enc"),
        key=lambda ruta: ruta.name,
        reverse=True,
    )


def aplicar_retencion(
    directorio: str | Path,
    *,
    tipo: str = "diario",
    conservar: int | None = None,
) -> list[Path]:
    """Conserva los últimos N backups de un tipo y elimina los anteriores."""
    if tipo not in _TIPOS:
        raise ErrorBackup(f"Tipo de backup inválido: {tipo!r}.")
    if conservar is None:
        conservar = {
            "diario": BACKUP_RETENTION_DAILY,
            "semanal": BACKUP_RETENTION_WEEKLY,
            "offline": BACKUP_RETENTION_OFFLINE,
        }[tipo]
    if conservar < 0:
        raise ErrorBackup("La retención no puede ser negativa.")

    directorio_path = Path(directorio).expanduser()
    archivos = _archivos_backup(directorio_path, tipo)
    eliminados: list[Path] = []
    for archivo in archivos[conservar:]:
        archivo.unlink(missing_ok=True)
        _ruta_checksum(archivo).unlink(missing_ok=True)
        eliminados.append(archivo)
    return eliminados


def copiar_offline(
    *,
    directorio_semanal: str | Path | None = None,
    directorio_offline: str | Path | None = None,
) -> BackupInfo:
    """Copia el backup semanal más reciente al medio offline."""
    if directorio_semanal is None:
        from ventas_app.config import BACKUP_DIR

        directorio_semanal = BACKUP_DIR
    if directorio_offline is None:
        from ventas_app.config import BACKUP_OFFLINE_DIR

        directorio_offline = BACKUP_OFFLINE_DIR
    semanales = _archivos_backup(
        Path(directorio_semanal).expanduser(),
        "semanal",
    )
    if not semanales:
        raise ErrorBackup("No hay backups semanales para copiar offline.")
    origen = semanales[0]
    if not verificar_backup(origen):
        raise ErrorBackup("El backup semanal no pasó la verificación.")

    destino_dir = Path(directorio_offline).expanduser()
    destino_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        destino_dir.chmod(0o700)
    except OSError:
        pass
    nombre_offline = origen.name.replace("-semanal.db.enc", "-offline.db.enc")
    if nombre_offline == origen.name:
        raise ErrorBackup("El nombre del backup semanal no es reconocible.")
    destino = destino_dir / nombre_offline
    shutil.copy2(origen, destino)
    _escribir_privado(destino, destino.read_bytes())
    _escribir_privado(
        _ruta_checksum(destino),
        _ruta_checksum(origen).read_bytes(),
    )
    aplicar_retencion(destino_dir, tipo="offline")
    return BackupInfo(
        ruta=destino,
        checksum=_ruta_checksum(destino).read_text(encoding="ascii").strip(),
        bytes=destino.stat().st_size,
    )


def listar_backups(directorio: str | Path | None = None) -> list[Path]:
    """Lista backups cifrados ordenados por nombre descendente."""
    if directorio is None:
        from ventas_app.config import BACKUP_DIR

        directorio = BACKUP_DIR
    return sorted(
        Path(directorio).expanduser().glob("ventas-*.db.enc"),
        key=lambda ruta: ruta.name,
        reverse=True,
    )


def _iterar_archivos(rutas: Iterable[Path]) -> list[Path]:
    return list(rutas)


__all__ = [
    "BackupInfo",
    "ErrorBackup",
    "aplicar_retencion",
    "copiar_offline",
    "crear_backup",
    "listar_backups",
    "restaurar_backup",
    "verificar_backup",
]
