# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 22 — F23: autenticación local, MFA y RBAC

---
feature: F23
fecha: 2026-11-23
tests: 366 passed
harness: OK
commit: feat(F23): autenticación local, MFA y RBAC
---

**Fecha:** 2026-11-23

**Rol:** Verifier. **Feature:** F23 — Autenticación local, MFA, sesiones y RBAC. **Estado:** verificada y aprobada.

Usuarios locales con Argon2id, sesiones opacas (solo hash en DB), CSRF de pre-sesión y por sesión, expiración idle 30 min/absoluta 8 h, rotación y revocación, MFA TOTP obligatorio para ADMIN/AUDITOR con recovery codes de un solo uso, bootstrap y CLI de usuarios, y RBAC OPERADOR/AUDITOR/ADMIN en HTML y API.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 366 passed; `node --check` → OK; CLI `--help` y bootstrap único → OK. 111 verificaciones manuales con TestClient sobre base temporal: 303/401 sin sesión, login genérico, rate limit/lockout, cookie flags (HttpOnly/Secure/SameSite), CSRF faltante/ajeno, MFA setup/challenge/replay/recovery, matriz RBAC e IDOR, idle/absoluta/revocación, desactivación, flujos existentes y ausencia de secretos en logs/`security_events`. `ventas.db` y `.env` locales intactos (600). Checklist F23 completo; riesgos residuales medios de rate limit MFA y `sessionStorage` previo quedan en F24/F25.

**Próximo paso:** F24 — Hardening HTTP, errores seguros y anti-abuso — packet: `features/F24.md`.

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
