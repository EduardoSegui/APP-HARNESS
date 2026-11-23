# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 23 — F24: hardening HTTP y anti-abuso

---
feature: F24
fecha: 2026-11-23
tests: 377 passed
harness: OK
commit: feat(F24): hardening HTTP y anti-abuso
---

**Fecha:** 2026-11-23

**Rol:** Verifier. **Feature:** F24 — Hardening HTTP, errores seguros y anti-abuso. **Estado:** verificada y aprobada.

Middleware de CSP/headers (`nosniff`, `DENY`, `no-referrer`, `Permissions-Policy`, `noindex`, `no-store`), HSTS opt-in y `TrustedHost` configurable; docs/OpenAPI cerrados por defecto; body 256 KB, 20 integrantes, `q` 100, page size 100 y export 5.000 filas; rate limiting por IP/política; lock de auditoría con 409; 422 sanitizado sin `input`/`ctx`; access logs sin query; credencial sin `onclick` y con JS externo.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 377 passed. 54 verificaciones manuales TestClient sobre base temporal: headers/CSP en HTML/API, HSTS opt-in, TrustedHost, docs 404, 413, 422 de integrantes/búsqueda/export/PAN/CBU/DDJJ sin filtrar datos, lock 409, logs propios y de Uvicorn sin query, JS externo, y flujos F23 (login, CSRF y RBAC). Rate limit real: 31 POST → 429 y 61 búsquedas → 429. `ventas.db` real intacta.

**Próximo paso:** F25 — Protección de PII/salud, secretos, MCP y LLM — packet: `features/F25.md`.

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
