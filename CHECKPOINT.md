# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 20 — F21: wizard con sticky rail y navegación libre

---
feature: F21
fecha: 2026-11-20
tests: 358 passed
harness: OK
commit: feat(F21): wizard con sticky rail y navegación libre
---

**Fecha:** 2026-11-20

**Rol:** Verifier. **Feature:** F21 — Wizard con sticky rail y navegación libre. **Estado:** verificada y aprobada.

`#wizard-sidebar` unifica rail y resumen sticky en escritorio y se apila en móvil. Las tres solapas navegan libremente sin validar, conservan datos en DOM/estado y muestran activo/pendiente/completado con check verde. La confirmación valida 1–3 y redirige al primer paso inválido. Los indicadores se recalculan al cambiar DDJJ (radios, detalle y confirmación) y al editar cualquier campo de tarjeta/CBU; el checkbox DDJJ quedó inline 18×18.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 358 passed; `node --check` → OK. Chrome headless sobre base temporal: sticky top 20 al scrollear, static en 390px, gap rail/resumen 16px, checkbox 18×18 inline; navegación libre y conservación en alta y edición; check de paso 1 baja/sube al desmarcar/reconfirmar DDJJ y al escribir/borrar detalle; check de paso 3 cambia al completar/borrar tarjeta y CBU; confirmación con faltantes va a pasos 1 y 2; alta POST y edición PUT con comprobante. Endpoints `/health`, `/api/ventas`, detalle, `/ventas`, `/dashboard` y `/api/metricas` OK.

**Próximo paso:** F22 — Tablero con KPIs, barras y filtros de exportación — packet: `features/F22.md`.

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
