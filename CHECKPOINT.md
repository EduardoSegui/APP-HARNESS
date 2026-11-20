# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 11 — F12: rediseño visual del wizard y el panel

---
feature: F12
fecha: 2026-11-19
tests: 206 passed
harness: OK
commit: feat(F12): rediseño visual del wizard y panel
---

**Fecha:** 2026-11-19

**Rol:** Builder + Verifier (fases separadas). **Feature:** F12 — Rediseño visual del wizard y el panel. **Estado:** verificada y aprobada.

Aplicar la identidad “legajo de alta / mesa de entradas” con `frontend-design`, sin tocar lógica, API, DB ni contratos JS. Entregables:

- `design.css` con tokens, shell, hojas, campos, sellos, planilla, acta y responsive; templates `base`, `wizard`, `panel` y `comprobante`.
- `wizard.js` con resumen del legajo y sello del comprobante; `auditoria.js` con sellos semánticos; `tests/test_ui_design.py` y aserciones visuales del panel.
- `docs/design/F12.md` con la revisión visual.

**Verificación:** `./init.sh` y `uv run pytest` → OK, 206 passed. 360/768/1280 sin desborde; wizard, comprobante, panel vacío, tabla, acta y traza revisados; formulario inválido con 6 errores y foco; auditoría en vivo actualiza sellos y observaciones.

**Decisiones:** audacia en rail de solapas y sellos; sin card soup, eyebrows en mayúsculas ni gradientes. “Pendiente/Aprobada/Observada” visibles; `data-estado` conserva el enum. Bricolage Grotesque + Public Sans; tinta/papel/verde/vino/mostaza.

**Próximo paso:** no quedan features pendientes; planificar con `features/_TEMPLATE.md` antes de construir.

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
