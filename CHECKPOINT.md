# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 21 — F22: Tablero con KPIs, barras y filtros de exportación

---
feature: F22
fecha: 2026-11-20
tests: 359 passed
harness: OK
commit: feat(F22): tablero con KPIs, barras y filtros
---

**Fecha:** 2026-11-20

**Rol:** Verifier. **Feature:** F22 — Tablero con KPIs, barras y filtros de exportación. **Estado:** verificada y aprobada.

KPIs separados en “Operación y padrón” (ventas, tasa de aprobación, cobertura) y “Finanzas” (MRR, recaudación, ticket). Distribuciones por plan/medio/régimen con porcentaje y `.prop-bar`; motivos R1–R8 con etiqueta, cantidad, porcentaje, barra y reglas en cero atenuadas. Filtro Estado en dashboard, `/api/metricas` y exportaciones; export por defecto aprobadas, estado explícito exporta ese subconjunto. URLs de exportación conservan `desde`, `hasta`, `plan_id` y `estado`, con badge cuando hay filtros activos.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 359 passed. Smoke TestClient sobre base temporal: 2 aprobadas + 2 observadas + 1 pendiente, porcentajes 50/50, motivos 50/25/25, filtros por estado, export default/observada/pendiente, URLs y badge, vacíos, 400/422 y ausencia de PAN/CVV/CBU/CUIL completos. Chrome headless a 1280/900/390 px sin desbordes. `ventas.db` real intacta.

**Próximo paso:** no quedan features pendientes; corresponde planificación (SDD pasos 1–5) antes de construir.

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
