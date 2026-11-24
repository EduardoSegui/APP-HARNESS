"""Semilla efímera para el admin de la demo E2E."""

from __future__ import annotations

import os

from ventas_app.database import SessionLocal, init_db
from ventas_app.models import RolUsuario, Usuario
from ventas_app.security import cifrar_secreto, hash_password


def main() -> None:
    username = os.environ["E2E_ADMIN_USER"]
    password = os.environ["E2E_ADMIN_PASSWORD"]
    secret = os.environ["E2E_ADMIN_MFA_SECRET"]
    init_db()
    with SessionLocal() as db:
        usuario = db.query(Usuario).filter_by(username=username).one_or_none()
        if usuario is None:
            usuario = Usuario(
                username=username,
                password_hash=hash_password(password),
                rol=RolUsuario.ADMIN.value,
                activo=True,
                mfa_enabled=True,
                mfa_secret_enc=cifrar_secreto(secret),
            )
            db.add(usuario)
        else:
            usuario.password_hash = hash_password(password)
            usuario.mfa_enabled = True
            usuario.mfa_secret_enc = cifrar_secreto(secret)
        db.commit()


if __name__ == "__main__":
    main()
