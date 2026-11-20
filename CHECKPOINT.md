# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 12 — F13: medios de pago y descuentos en cotización

---
feature: F13
fecha: 2026-11-20
tests: 252 passed
harness: OK
commit: feat(F13): medios de pago y descuentos en cotización
---

**Fecha:** 2026-11-20

**Rol:** Verifier (Builder en sesión previa). **Feature:** F13 — Medios de pago y descuentos en cotización. **Estado:** verificada y aprobada.

`MedioPago` con tarjeta 30%, CBU 20% y Pago Fácil/Cobrador 0%; `POST /api/ventas` exige `medio_pago` (422 si falta o es inválido) y persiste `subtotal_base`, `descuento_porcentaje` y `precio_total` con redondeo half-up compartido con el wizard. Comprobante y panel muestran el desglose; R5 valida plan, medio, subtotal, descuento y total. Migración SQLite idempotente para bases F12 en `init_db()` y al arrancar el MCP.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 252 passed. Prueba manual con TestClient sobre copia temporal de `ventas.db`: CBU 130.000 → 104.000, 422 sin medio e inválido, R5 detecta total adulterado, panel y wizard con desglose. `ventas.db` real sin modificar.

**Decisión:** el redondeo se centraliza en `pricing.py` y replica `Math.round`; las filas históricas quedan en `PAGO_FACIL`, descuento 0 y `subtotal_base=precio_total`.

**Próximo paso:** no quedan features pendientes; planificar con `features/_TEMPLATE.md` antes de construir.

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
