# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 15 — F16: declaración jurada de salud y R7

---
feature: F16
fecha: 2026-11-20
tests: 310 passed
harness: OK
commit: feat(F16): declaración jurada de salud y R7
---

**Fecha:** 2026-11-20

**Rol:** Verifier (Builder en sesión previa). **Feature:** F16 — Declaración jurada de salud y auditoría médica. **Estado:** verificada y aprobada.

`Venta` persiste `ddjj_completada`, los cinco indicadores y `ddjj_detalle`; la migración SQLite idempotente agrega las columnas y deja las filas históricas sin DDJJ. `SaludIn` exige `declaracion_confirmada=true` y detalle (5–2000 caracteres) cuando hay indicadores; `VentaIn`/`VentaUpdateIn` exigen `ddjj` y el servicio persiste la declaración confirmada en altas y ediciones. R7 observa DDJJ incompletas, detalle faltante y deriva a revisión médica preexistencias, internaciones o discapacidad; embarazo y medicación con detalle no generan R7 en v1. El wizard exige confirmación, el comprobante/panel muestran el estado resumido y el detalle de salud queda solo en el legajo, fuera de `sessionStorage` y del listado general.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 310 passed; `node --check wizard.js` → OK. Prueba manual con TestClient sobre copia temporal de `ventas.db`: R7 sin observaciones sin riesgo, derivación con preexistencia/internación/discapacidad, 422 sin detalle/sin DDJJ/sin confirmación, venta histórica observada y completada vía PUT, edición de riesgo a sin riesgo, badges del panel y ausencia del detalle sensible en el listado. `ventas.db` real sin modificar.

**Decisión:** R7 es determinística y solo deriva; el detalle declarado se minimiza a la ficha interna del legajo.

**Próximo paso:** F17 — Régimen de afiliación, CUIL y aportes — packet: `features/F17.md`.

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
