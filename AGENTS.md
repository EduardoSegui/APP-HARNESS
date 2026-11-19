# AGENTS.md — Punto de entrada del harness

Aplicación web de ventas de obra social: FastAPI + SQLAlchemy/SQLite + Jinja2, con servidor MCP local y Agente Auditor. El desarrollo se rige bajo **Spec-Driven Development (SDD)** en 7 pasos (Constitución, Especificación, Clarificación, Planificación, Tareas, Implementación y Validación) con dos roles aislados: Builder y Verifier.

## Empezar una sesión

1. Leé `STATE.md`: estado actual y próximo paso.
2. Si hay una feature pendiente, leé solo su ficha `features/F0X.md` y las secciones de `docs/` que cite. Si no hay ficha, planificá antes de construir.
3. Leé el rol que vas a ejercer: `.agent/subagents/builder.md` o `verifier.md`.
4. Consultá `CONSTITUTION.md` para los principios inmutables y `.agent/rules.md` para el protocolo operativo.

No leas `PRD.md`, `ARQUITECTURA.md` ni el historial completos. En OpenCode podés usar `/sesion` para inyectar `STATE.md` + `git status` + `git log -5`.

## Comandos

Todos desde la raíz del repositorio. Python y tests siempre con `uv run`.

```bash
./init.sh
uv run pytest
uv run uvicorn ventas_app.main:app --reload --port 8000
uv run python scripts/cargar_demo.py
uv run python -m ventas_app.mcp_server
uv run python -m ventas_app.auditor
```

## Reglas duras (Constitución Operativa)

- Principios inmutables: cumplimiento estricto de `CONSTITUTION.md`.
- Una feature por sesión: la primera con `"passes": false` en `features.json`.
- No marcar `"passes": true` sin `./init.sh` + `uv run pytest` + prueba manual.
- No adelantar features ni mezclar refactors ajenos.
- Sin `python`, `python3`, `pytest` o `pip` directos; siempre `uv run` / `uv add`.
- No editar `ventas.db` a mano; no versionar secretos, bases ni artefactos.
- No cambiar alcance sin actualizar antes `docs/` y `features.json`.
- Sin ficha (`features/F0X.md`) no se construye: si no hay feature pendiente, se planifica; no se inventa alcance.
- Toda feature nueva debe clarificar ambigüedades con el usuario antes de codificar.
- Una ficha se crea desde `features/_TEMPLATE.md` y se registra en `features.json` con `"packet"`.
- Al cerrar: `features.json`, `STATE.md` regenerado, bitácora, `./init.sh` y commit.

## Router de contexto

| Necesitás | Leé |
|---|---|
| Constitución y principios inmutables | `CONSTITUTION.md` |
| Estado actual y próximo paso | `STATE.md` |
| Plan y progreso | `features.json` |
| Ficha de la feature pendiente | `features/F0X.md` |
| Plantilla de ficha SDD | `features/_TEMPLATE.md` |
| Protocolo de sesión y cierre | `.agent/rules.md` |
| Historia y decisiones | `docs/journal/` y `CHECKPOINT.md` (solo la entrada que necesites) |
| Spec funcional | `docs/PRD.md`, solo la sección citada |
| Diseño técnico | `docs/ARQUITECTURA.md`, solo la sección citada |
| Mapa de documentación | `docs/INDEX.md` |
| Rol de implementación | `.agent/subagents/builder.md` |
| Rol de verificación | `.agent/subagents/verifier.md` |
| Presupuesto de contexto | `uv run python scripts/contexto.py --check` |

## Fuente de verdad

`features.json` es la verdad del progreso. `STATE.md` es la foto actual. `CHECKPOINT.md` conserva las últimas 2 sesiones; lo anterior está en `docs/journal/`. No dupliques un dato en varios archivos: si cambia, actualizá el lugar canónico y los enlaces.

## Roles

| Rol | Archivo | Cuándo |
|---|---|---|
| Builder | `.agent/subagents/builder.md` | Implementar la feature pendiente y sus tests. |
| Verifier | `.agent/subagents/verifier.md` | Verificar, marcar `passes`, registrar el cierre y commitear. |

El Builder nunca marca `passes`; el Verifier nunca implementa lógica nueva.
