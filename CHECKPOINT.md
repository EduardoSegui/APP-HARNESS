# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 17 — F20: DDJJ con respuestas Sí/No y detalle condicional

---
feature: F20
fecha: 2026-11-20
tests: 338 passed
harness: OK
commit: feat(F20): DDJJ con respuestas Sí/No y detalle condicional
---

**Fecha:** 2026-11-20

**Rol:** Verifier (Builder en sesión previa). **Feature:** F20 — Mejora DDJJ con respuestas Sí/No y detalle condicional. **Estado:** verificada y aprobada.

La DDJJ usa cinco `fieldset` con radios Sí/No (`si`/`no`), estado JS `true`/`false`/`null` y validación que exige las cinco respuestas. La descripción queda siempre visible, es obligatoria ante cualquier “Sí” y opcional si todas son “No”; la confirmación expresa sigue siendo obligatoria. El resumen lateral muestra Pendiente/Sin confirmar/Revisión médica/Completa. Backend, API y R7 se conservan sin cambios; la DDJJ sigue fuera de `sessionStorage`.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 338 passed; `node --check wizard.js` → OK. Prueba manual con TestClient sobre base temporal: 5 grupos Sí/No y descripción visible, todas “No” sin descripción → 201, “Sí” sin descripción → 422, “Sí” con descripción → 201, sin confirmación → 422, edición F16 con respuestas/detalle precargados, panel/legajo/R7 conservados. `ventas.db` real sin modificar.

**Decisión:** el backend mantiene el contrato de F16; F20 cambia solo la experiencia y la validación de completitud en la UI.

**Próximo paso:** F18 — Buscador, filtros, linaje y credencial — packet: `features/F18.md`.

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
