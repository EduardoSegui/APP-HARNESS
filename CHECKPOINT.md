# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 28 — F29: hardening de seguridad y datos

---
feature: F29
fecha: 2026-11-24
tests: 416 passed
harness: OK
commit: feat(F29): hardening de seguridad y datos
---

**Fecha:** 2026-11-24

**Rol:** Verifier. **Feature:** F29 — Hardening de seguridad y datos. **Estado:** verificada y aprobada.

Cifrado falla seguro ante tokens de otra clave sin re-cifrar ni exponerlos; MFA con rate limit y revocación de sesión pendiente a los 5 fallos. Eventos nuevos e históricos redactan DNI/CUIL/email/teléfono, registran username real (o `mcp-auditor`) y el DSR restaura triggers append-only tras backup verificado. `VentaUpdateIn.version` obligatoria (422/409) y legajo con CUIL enmascarado.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 416 passed; pruebas manuales TestClient/SQLite sobre base temporal: 32 comprobaciones (clave ajena y no modificación, MFA 5 fallos/429 y flujo válido, eventos nuevos/históricos sin PII, actor real, 422/409, CUIL/CBU enmascarados, triggers y regresiones F23–F28). Checklist F29 completo; sin Critical/High abiertos.

**Próximo paso:** Plan completo (29/29); F30/F31 no planificadas.

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
