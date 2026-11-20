# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 19 — F19: Tablero analítico y exportación

---
feature: F19
fecha: 2026-11-20
tests: 358 passed
harness: OK
commit: feat(F19): tablero analítico y exportación
---

**Fecha:** 2026-11-20

**Rol:** Verifier. **Feature:** F19 — Tablero analítico y exportación. **Estado:** verificada y aprobada.

El tablero `GET /dashboard` y `GET /api/metricas` exponen embudo, cobertura, MRR bruto, descuentos, aportes, recaudación neta, tickets, distribuciones y ranking R1–R8. Las exportaciones `GET /api/exportar/padron|cobranzas?formato=csv|json` filtran por fecha/plan, usan encabezados estables y enmascaran instrumentos y CUIL. El descuento agregado se redondea half-up por venta con `cast((subtotal * porcentaje + 50) / 100, Integer)`; el nuevo test de tres aprobadas verifica 220.000/48.000/15.000/157.000.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 358 passed. Smoke con TestClient sobre base temporal: dashboard y API consistentes, descuentos 48.000 (no 48.001), identidad neta, exportaciones CSV/JSON cuyas filas suman MRR/descuentos/aportes/neto, filtros por plan y fecha, estados vacíos, errores 400/422 y ausencia de PAN/CVV/CBU completos, CUIL sin enmascarar y datos de salud. `ventas.db` real sin modificar.

**Decisión:** el redondeo por venta usa el mismo criterio que `pricing.calcular_descuento_monto`; las filas exportadas reconcilian exactamente con los agregados.

**Próximo paso:** no quedan features pendientes; corresponde planificar (SDD pasos 1–5) antes de construir.

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
