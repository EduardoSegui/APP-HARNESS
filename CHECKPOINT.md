# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 13 — F14: instrumentos de pago enmascarados

---
feature: F14
fecha: 2026-11-20
tests: 274 passed
harness: OK
commit: feat(F14): instrumentos de pago enmascarados
---

**Fecha:** 2026-11-20

**Rol:** Verifier (Builder en sesión previa). **Feature:** F14 — Instrumentos de pago: tarjeta y CBU con datos enmascarados. **Estado:** verificada y aprobada.

`TarjetaMarca` + `TarjetaIn`/`CbuIn` validan formato y vencimiento; `VentaIn` exige y hace coherente el instrumento con `medio_pago`. Se persisten solo `pago_titular`, `pago_marca_entidad`, `pago_ultimos_4`, `pago_vencimiento` y `pago_cuil`; nunca PAN/CBU completo ni CVV. `VentaOut`, panel y MCP muestran el instrumento enmascarado; R5 valida metadatos; migración SQLite idempotente agrega las cinco columnas y conserva filas F13.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 274 passed. Prueba manual con TestClient sobre copia temporal de `ventas.db`: tarjeta (VISA •••• 1111) y CBU (Banco Ejemplo •••• 0123), 8 casos 422, DB y respuesta sin PAN/CVV, panel enmascarado, R5/MCP con descuento y venta histórica observada. `ventas.db` real sin modificar.

**Decisión:** el CVV se valida en memoria y se descarta; los datos demo usan instrumentos ficticios.

**Próximo paso:** F15 — Ver, reabrir y editar ventas por etapas — packet: `features/F15.md`.

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
