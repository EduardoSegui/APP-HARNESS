"""CLI administrativa de usuarios locales."""

from __future__ import annotations

import argparse
import getpass
import sys

from ventas_app.database import SessionLocal, init_db
from ventas_app.models import RolUsuario
from ventas_app.services.usuarios import (
    PasswordDebilError,
    UsuarioYaExisteError,
    activar_usuario,
    bootstrap_admin,
    crear_usuario,
    desactivar_usuario,
    obtener_por_username,
    resetear_password,
)


def _password_confirmada() -> str:
    password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    repetida = getpass.getpass("Repetí la contraseña: ")
    if password != repetida:
        raise ValueError("Las contraseñas no coinciden.")
    return password


def _bootstrap() -> int:
    username = input("Usuario ADMIN: ").strip()
    try:
        password = _password_confirmada()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        try:
            usuario = bootstrap_admin(
                db,
                username=username,
                password=password,
            )
        except (UsuarioYaExisteError, PasswordDebilError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    print(f"ADMIN '{usuario.username}' creado. El próximo login exigirá MFA.")
    return 0


def _crear() -> int:
    username = input("Usuario: ").strip()
    rol_raw = input("Rol [OPERADOR/AUDITOR/ADMIN]: ").strip().upper()
    try:
        rol = RolUsuario(rol_raw)
        password = _password_confirmada()
    except (ValueError, PasswordDebilError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        try:
            usuario = crear_usuario(
                db,
                username=username,
                password=password,
                rol=rol,
            )
        except (UsuarioYaExisteError, PasswordDebilError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    print(f"Usuario '{usuario.username}' creado con rol {usuario.rol}.")
    return 0


def _reset() -> int:
    username = input("Usuario: ").strip()
    with SessionLocal() as db:
        usuario = obtener_por_username(db, username)
        if usuario is None:
            print("Error: usuario inexistente.", file=sys.stderr)
            return 1
        try:
            password = _password_confirmada()
            resetear_password(db, usuario, password)
        except (PasswordDebilError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    print("Contraseña actualizada; las sesiones existentes deben revocarse.")
    return 0


def _desactivar(activar: bool) -> int:
    username = input("Usuario: ").strip()
    with SessionLocal() as db:
        usuario = obtener_por_username(db, username)
        if usuario is None:
            print("Error: usuario inexistente.", file=sys.stderr)
            return 1
        if activar:
            activar_usuario(db, usuario)
        else:
            desactivar_usuario(db, usuario)
    print(("Usuario activado." if activar else "Usuario desactivado."))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Usuarios locales")
    parser.add_argument(
        "comando",
        choices=[
            "admin-bootstrap",
            "user-create",
            "user-reset-password",
            "user-disable",
            "user-enable",
        ],
    )
    args = parser.parse_args(argv)
    init_db()
    if args.comando == "admin-bootstrap":
        return _bootstrap()
    if args.comando == "user-create":
        return _crear()
    if args.comando == "user-reset-password":
        return _reset()
    if args.comando == "user-disable":
        return _desactivar(False)
    return _desactivar(True)


if __name__ == "__main__":
    raise SystemExit(main())
