# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 16 — F17: régimen de afiliación, CUIL y aportes

---
feature: F17
fecha: 2026-11-20
tests: 338 passed
harness: OK
commit: feat(F17): régimen de afiliación, CUIL y aportes
---

**Fecha:** 2026-11-20

**Rol:** Verifier (Builder en sesión previa). **Feature:** F17 — Régimen de afiliación, CUIL y aportes estimados. **Estado:** verificada y aprobada.

`Venta` persiste `regimen_afiliacion` (default `PARTICULAR`), `cuil_titular` y `aporte_estimado`; `POST`/`PUT` validan CUIL de 11 dígitos para desregulados, aporte 0 para particulares y aporte ≤ base bonificada. El pricing calcula `base_bonificada = subtotal - descuento` y `precio_total = max(0, base_bonificada - aporte)`. R8 observa régimen inválido, CUIL faltante/incorrecto y aporte excesivo; R5 descuenta el aporte del total esperado. El wizard muestra CUIL/aporte solo para desregulados; panel, legajo y comprobante exhiben régimen y aporte, con CUIL enmascarado.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 338 passed; `node --check wizard.js` → OK. Prueba manual con TestClient sobre copia temporal de `ventas.db`: particular 45.000, relación de dependencia 45.000−20.000=25.000, monotributo con aporte igual a la base → total 0; 422 por particular con aporte, desregulado sin CUIL, CUIL inválido y aporte > base; PUT F15 cambia régimen/aporte y recalcula; R5/R8 observan; panel/legajo/comprobante OK. Migración con hijos: 7 ventas y 3 integrantes antes/después, ids conservados, CHECK `>= 0`, índices y FKs intactos, `PRAGMA foreign_key_check` vacío, idempotente. `ventas.db` real sin modificar.

**Decisión:** el fix de migración respalda y reinserta `integrantes` antes/después del `DROP TABLE ventas`, porque el cascade de SQLite elimina los hijos aunque las FKs estén diferidas.

**Próximo paso:** F18 — Buscador, filtros, linaje y credencial — packet: `features/F18.md`.

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
