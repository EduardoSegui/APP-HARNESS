# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 24 — F25: protección de PII/salud, secretos, MCP y LLM

---
feature: F25
fecha: 2026-11-23
tests: 389 passed
harness: OK
commit: feat(F25): protección de PII/salud, secretos, MCP y LLM
---

**Fecha:** 2026-11-23

**Rol:** Verifier. **Feature:** F25 — Protección de PII/salud, secretos, MCP y LLM. **Estado:** verificada y aprobada.

Cifrado en reposo de `ddjj_detalle` con Fernet/`EncryptedText`, validación criptográfica de tokens (no por prefijo `gAAAA`) y migración idempotente de históricos; lectura sin 500 ante valores no descifrables. Listado API con `VentaResumenOut` sin salud/contacto/CUIL/instrumentos y detalle autorizado completo. MCP local por `stdio` con allowlist de entorno, sin `OPENAI_API_KEY`/`APP_ENCRYPTION_KEY`, sin `.env` y salud solo como `[cifrado]`. `sessionStorage` conserva solo `paso`/`plan_id`. `LLMProvider` local por defecto y externo opt-in por HTTPS que recibe solo conteos/códigos R1–R8, con evento `LLM_EXTERNO` sin PII. `.env` y DB con permisos `600`.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 389 passed; 12 casos en `tests/test_privacy.py`; `node --check` de wizard/auditoría/credencial → OK; 10 verificaciones manuales TestClient/MCP/Node y re-verificación del borde `gAAAA...` (cifrado real, `descifrar_texto(crudo) == detalle`, migración de fila histórica, GET 200 y sin 500) + smoke F23/F24. Checklist F25 completo; sin Critical/High abiertos.

**Próximo paso:** F26 — Durabilidad, backups, concurrencia e inmutabilidad — packet: `features/F26.md`.

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
