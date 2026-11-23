# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 25 — F26: durabilidad, backups, concurrencia e inmutabilidad

---
feature: F26
fecha: 2026-11-23
tests: 397 passed
harness: OK
commit: feat(F26): durabilidad, backups, concurrencia e inmutabilidad
---

**Fecha:** 2026-11-23

**Rol:** Verifier. **Feature:** F26 — Durabilidad, backups, concurrencia e inmutabilidad. **Estado:** verificada y aprobada.

SQLite en WAL, `busy_timeout`, `synchronous=FULL`, claves foráneas y `integrity_check`/`foreign_key_check` al iniciar; backups cifrados con checksum, retención 7+4+1, copia offline renombrada y restore verificado; `Venta.version` con 409 y `venta_eventos` append-only por triggers.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 397 passed; 67 comprobaciones manuales TestClient/SQLite sobre base temporal (PRAGMAs, integridad, backup cifrado sin PII en claro, permisos 600/700, corrupción/checksum inválido, dos semanales con una sola copia offline, restore con triggers, versión 409, compatibilidad sin versión, CSV/CLI, migración) + CLI backup/restore y `node --check`; F23–F25 intactos; `ventas.db` real sin cambios. Checklist F26 completo; sin Critical/High abiertos.

**Próximo paso:** F27 — Privacidad, retención, legal hold y seguridad operativa — packet: `features/F27.md`.

## Sesión 26 — F27: privacidad, retención, legal hold y DSR

---
feature: F27
fecha: 2026-11-23
tests: 406 passed
harness: OK
commit: feat(F27): privacidad, retención, legal hold y DSR
---

**Fecha:** 2026-11-23

**Rol:** Verifier. **Feature:** F27 — Privacidad, retención, legal hold y seguridad operativa. **Estado:** verificada y aprobada.

`security_events` sin PII con IP minimizada para login/MFA, denegaciones RBAC, exportaciones, credencial, auditoría, usuarios, backups/restore, retención, legal hold y DSR. Retención por categoría (SEGURIDAD 365 días; COMERCIAL/SALUD sin auto-borrado), job que solo elimina eventos vencidos y deja evidencia. Legal hold bloquea supresión/anonimización; DSR de acceso, rectificación, supresión y anonimización auditados. Anonimización elimina PII/salud (incluida `fecha_nacimiento_titular` y DNI) conservando venta y linaje, y exige backup verificado + `--confirmar`. Aviso versionado en `/privacidad` y consentimiento registrado en el wizard.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 406 passed; `tests/test_privacidad_f27.py` → 9 passed; `node --check` OK; pruebas manuales TestClient/SQLite/CLI sobre base temporal: rechazo sin backup/confirmación o con backup corrupto sin modificar datos, anonimización con backup real, holds bloqueando DSR, retención selectiva, eventos sin PII y F23–F26 intactos. Checklist F27 completo; sin Critical/High abiertos.

**Próximo paso:** F28 — Cadena de suministro y SDD seguro — packet: `features/F28.md`.
