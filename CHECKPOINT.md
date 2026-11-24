# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 29 — F30: administración excepcional de ventas

---
feature: F30
fecha: 2026-11-24
tests: 425 passed
harness: OK
commit: feat(F30): administración excepcional de ventas
---

**Fecha:** 2026-11-24

**Rol:** Verifier. **Feature:** F30 — Administración excepcional de ventas. **Estado:** verificada y aprobada.

Reapertura ADMIN de ventas aprobadas con motivo, versión y evento de actor real; la venta vuelve a `PENDIENTE_VERIFICACION` y exige reauditoría. Baja lógica con motivo, versión, legal hold bloqueante y conservación de fila/eventos; excluida de panel, API, métricas, exportaciones y MCP. Botones admin en panel/legajo, confirmación explícita y JS sin handlers inline.

**Verificación:** `./init.sh` → OK (gate incluido); `uv run pytest` → 425 passed; 89 comprobaciones manuales TestClient/SQLite/MCP sobre base temporal: reapertura y reauditoría, RBAC OPERADOR/AUDITOR 403, CSRF 403, 422 sin motivo/versión, 409 obsoleta/estado, baja lógica con fila y eventos conservados, filtros panel/API/métricas/export/MCP, legal hold 409 sin cambios, UI admin/operador y regresiones F23–F29; migración de columnas validada. Checklist F30 completo; sin Critical/High abiertos (riesgo residual bajo: DELETE sin política de rate limit específica).

**Próximo paso:** Plan completo (30/30); F31 no planificada.

## Sesión 30 — F31: E2E Playwright y video demo

---
feature: F31
fecha: 2026-11-24
tests: 425 passed + 1 e2e
harness: OK
commit: feat(F31): E2E Playwright y video demo
---

**Fecha:** 2026-11-24

**Rol:** Verifier. **Feature:** F31 — E2E Playwright y video demo. **Estado:** verificada y aprobada.

E2E Playwright con Chrome sobre Uvicorn/SQLite temporal, admin `demo-admin` con TOTP efímero y datos ficticios. Cubre login/MFA, alta, auditoría sin LLM, tablero, reapertura y baja con el diálogo modal de F30. `pytest` normal excluye E2E; `uv run pytest -m e2e` pasa. Demo regenerada con `scripts/record_demo.py` (~19,5 s; GIF 960×540 y MP4 1280×720).

**Verificación:** `./init.sh` → OK; `uv run pytest` → 425 passed, 1 deselected; `uv run pytest -m e2e` → 1 passed; suite combinada → 426 passed; caso borde del modal verificado (cancelar no envía, motivo corto no cierra); video sin secretos productivos ni PII real; proceso E2E detenido y DB en tmp de pytest. Checklist F31 completo; sin Critical/High abiertos (riesgos residuales bajos: credenciales de test fijas y DB temporal bajo retención de pytest).

**Próximo paso:** Plan completo (31/31); no hay features pendientes.
