# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 10 — Feature packets e intake

---
feature: F11
fecha: 2026-11-18
tests: 204 passed
harness: OK
commit: feat(F11): feature packets e intake
---

**Fecha:** 2026-11-18

**Rol ejercido:** Builder + Verifier (fases separadas)

**Feature:** F11 — Feature packets e intake

**Estado:** verificada y aprobada

### Objetivo

Agregar una ficha autocontenida por feature y el protocolo de planificación para abrir trabajo nuevo sin inferir alcance ni leer el PRD completo.

### Entregables

- `features/_TEMPLATE.md` con las secciones mínimas.
- `features/F11.md` como primera ficha real.
- `features.json` con el campo `packet` para F11.
- `.agent/rules.md` con el protocolo de planificación y la regla “sin ficha no se construye”.
- `AGENTS.md`, roles, `docs/INDEX.md`, `docs/ARQUITECTURA.md` y `README.md` actualizados.
- `scripts/contexto.py --check` exige ficha en toda feature pendiente.
- Tests de plantilla, ficha real, protocolo y cap de 8 KB.

### Verificación ejecutada

| Comprobación | Comando | Resultado |
|---|---|---|
| Harness completo | `./init.sh` | OK |
| Suite de tests | `uv run pytest` | `204 passed` |
| Presupuesto | `uv run python scripts/contexto.py --check` | OK |
| Ficha F11 | `wc -c features/F11.md` | 2.7 KB < 8 KB |

### Decisiones verificadas

- La ficha es la orden de trabajo; `features.json` es solo el índice.
- Toda feature pendiente debe declarar `packet`; el chequeo falla si falta.
- Las fichas se validan por secciones y por cap de 8 KB.
- No se reescribieron fichas de F01–F10.

### Próximo paso

No quedan features pendientes. Para abrir trabajo nuevo, usar la sesión de planificación: copiar `features/_TEMPLATE.md` a `features/F0X.md`, registrarla en `features.json` y recién después construir.

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
