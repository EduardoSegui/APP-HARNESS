# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 14 — F15: ver, reabrir y editar ventas por etapas

---
feature: F15
fecha: 2026-11-20
tests: 292 passed
harness: OK
commit: feat(F15): edición de ventas por etapas
---

**Fecha:** 2026-11-20

**Rol:** Verifier (Builder en sesión previa). **Feature:** F15 — Ver, reabrir y editar ventas por etapas. **Estado:** verificada y aprobada.

`VentaUpdateIn` reutiliza las validaciones comunes y permite omitir el instrumento para conservar los metadatos enmascarados; `PUT /api/ventas/{id}` responde 200 con recálculo, 400 plan inválido, 404 inexistente, 409 aprobada y 422 payload/instrumento inválido. `actualizar_venta` reemplaza el legajo y sus adherentes en una transacción, recalcula subtotal/descuento/total, limpia observaciones y vuelve a `PENDIENTE_VERIFICACION`; el wizard de edición precarga las tres etapas sin persistir datos sensibles, y el panel ofrece **Editar legajo** o **Ver legajo** según el estado.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 292 passed; `node --check wizard.js` → OK. Prueba manual con TestClient sobre copia temporal de `ventas.db`: 130.000 → 91.000 con tarjeta, conservación de tarjeta al omitir instrumento y cambiar de plan, observada → pendiente con observaciones `null`, alta/baja de adherentes, cambio tarjeta ↔ CBU y limpieza a Pago Fácil, 409/404/400/422, rollback total ante fallo de commit, rutas `/ventas/{id}/editar`, `/ventas/{id}` y acciones del panel. `ventas.db` real sin modificar.

**Decisión:** si el medio no cambia y el formulario de pago está vacío se conservan los metadatos; cualquier instrumento nuevo se revalida y reemplaza. La venta aprobada queda inmutable (la ficha HTML redirige 303; la API responde 409).

**Próximo paso:** F16 — Declaración jurada de salud y auditoría médica — packet: `features/F16.md`.

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
