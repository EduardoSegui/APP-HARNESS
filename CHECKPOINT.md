# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 09 — Memoria y contexto del harness (MVP F09 + F10)

---
feature: F09+F10
fecha: 2026-11-18
tests: 199 passed
harness: OK
commit: feat(F09-F10): memoria y contexto del harness
---

**Fecha:** 2026-11-18

**Rol ejercido:** Builder + Verifier (fases separadas)

**Features:** F09 (contexto always-on y estado) + F10 (bitácora rotativa, caps y `/sesion`)

**Estado:** verificadas y aprobadas

### Objetivo

Reducir el contexto que el agente lee al iniciar una sesión, reemplazar la lectura completa de la bitácora por un estado generado y evitar que el harness vuelva a crecer sin control.

### Entregables

- `AGENTS.md` liviano: comandos, reglas duras y router de contexto.
- `.agent/rules.md` y roles Builder/Verifier reducidos a su procedimiento.
- `STATE.md` generado por `scripts/contexto.py estado`; `--check` valida estado, packets y caps.
- `CHECKPOINT.md` como ventana de 2 sesiones; `docs/journal/2026.md` conserva F01–F08.
- `.opencode/commands/sesion.md`: inyecta estado, `git status` y `git log -5`.
- `init.sh` valida el presupuesto de contexto antes de pytest.
- `tests/test_contexto.py`: estado, caps, packets, rotación, CLI y comando.

### Verificación ejecutada

| Comprobación | Comando | Resultado |
|---|---|---|
| Harness completo | `./init.sh` | OK |
| Suite de tests | `uv run pytest` | `199 passed` |
| Estado generado | `uv run python scripts/contexto.py estado --stdout` | OK |
| Presupuesto | `uv run python scripts/contexto.py --check` | OK |
| Rotación | `uv run python scripts/contexto.py rotate` | F07–F08 archivadas |
| Comando `/sesion` | archivo y bloques shell revisados | OK |

### Decisiones verificadas

- `features.json` sigue siendo la fuente de verdad del progreso; `STATE.md` es la foto actual.
- `CHECKPOINT.md` no se lee completo: se conservan las últimas 2 sesiones y el resto queda en `docs/journal/`.
- Los caps se validan en `init.sh`; un archivo que crece hace fallar el harness.
- El MVP se ejecutó como una unidad de harness, con F09 y F10 verificadas en la misma sesión.
- F11 queda pendiente: packets e intake para la próxima feature.

### Archivos de la feature

```text
AGENTS.md
.agent/rules.md
.agent/subagents/builder.md
.agent/subagents/verifier.md
STATE.md
CHECKPOINT.md
docs/INDEX.md
docs/journal/2026.md
scripts/__init__.py
scripts/contexto.py
tests/test_contexto.py
.opencode/commands/sesion.md
init.sh
README.md
docs/ARQUITECTURA.md
features.json
pyproject.toml
```

### Git

- Commit de cierre: `feat(F09-F10): memoria y contexto del harness`.

### Próximo paso

F11 — Feature packets e intake: plantilla, packet autocontenido por feature y protocolo de planificación cuando no hay features pendientes.

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
