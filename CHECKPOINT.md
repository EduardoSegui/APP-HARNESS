# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 18 — F18: buscador, filtros, linaje y credencial

---
feature: F18
fecha: 2026-11-20
tests: 351 passed
harness: OK
commit: feat(F18): buscador, filtros, linaje y credencial
---

**Fecha:** 2026-11-20

**Rol:** Verifier. **Feature:** F18 — Buscador, filtros, linaje y credencial. **Estado:** verificada y aprobada.

Panel `GET /ventas` con `q` por DNI/nombre/apellido, filtros combinables por estado, plan, medio de pago y régimen, paginación de 20 y filtros preservados en formulario y links. `VentaEvento` registra CREADA/EDITADA/AUDITADA_APROBADA/AUDITADA_OBSERVADA con estados anterior/nuevo, detalle, actor y timestamp en la misma transacción; ficha con timeline; credencial provisoria solo para aprobadas, sin salud ni instrumentos de pago. API `GET /api/ventas` y `/api/ventas/{id}/eventos` con 422/404 defensivos.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 351 passed. Smoke con TestClient sobre base temporal: búsqueda DNI/apellido, filtros combinados preservados, 23 ventas en 2 páginas, eventos en orden con actores operador/auditor, rollback de edición sin evento falso, timeline, credencial aprobada sin DDJJ/tarjeta/CBU/CUIL y 404 para pendiente/observada, API filtrada y 422. Copia de `ventas.db`: `venta_eventos` creada con índices/CHECK, 7 ventas y 3 integrantes preservados; F17 intacto. `ventas.db` real sin modificar.

**Decisión:** la credencial usa `OS-{id:06d}` y la fecha de emisión es `actualizado_en`; los eventos se ordenan por `creado_en DESC, id DESC` para desempatar.

**Próximo paso:** F19 — Tablero analítico y exportación — packet: `features/F19.md`.

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
