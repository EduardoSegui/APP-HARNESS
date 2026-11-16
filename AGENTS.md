# AGENTS.md — Punto de Entrada del Proyecto

Este repositorio implementa una **aplicación web de carga de ventas de obra social** en tres etapas, con validación agéntica vía MCP, FastAPI y SQLite. El desarrollo se realiza con un harness de features atómicas y dos roles: Builder y Verifier.

## Lectura obligatoria al iniciar cualquier sesión

Antes de responder, planificar o modificar archivos, todo agente debe leer **en este orden**:

1. `.agent/rules.md` — reglas operativas obligatorias.
2. `CHECKPOINT.md` — memoria histórica y estado actual.
3. `features.json` — plan atómico y progreso real.
4. `docs/PRD.md` — especificación funcional.
5. `docs/ARQUITECTURA.md` — diseño técnico.
6. El rol correspondiente en `.agent/subagents/`.

No se debe escribir código hasta completar estas lecturas.

## Regla principal de trabajo

Trabajar **de a una feature por sesión**, tomando siempre la **primera con `"passes": false`** en `features.json`. No adelantar features, no mezclar alcances y no marcar `"passes": true` sin verificación completa (`./init.sh` + `uv run pytest` + pruebas manuales de la feature).

## Roles

| Rol | Archivo | Cuándo usarlo |
|---|---|---|
| **Builder** | `.agent/subagents/builder.md` | Para implementar la siguiente feature pendiente y sus tests. |
| **Verifier / QA** | `.agent/subagents/verifier.md` | Para ejecutar las verificaciones, probar casos borde, marcar `passes`, actualizar `CHECKPOINT.md` y commitear. |

Un mismo agente puede actuar como Builder y luego como Verifier, pero debe hacerlo en fases separadas y respetando los límites de cada rol. El Builder nunca marca `passes`; el Verifier nunca implementa lógica nueva.

## Estado actual del proyecto

- **Última sesión:** Sesión 01 — Inicialización del Harness.
- **Feature inicial:** F01 (estructura, SQLite y `/health`).
- **Próximo paso:** consultar `CHECKPOINT.md` y `features.json`; si F01 ya está aprobada, ejecutar F02.

La fuente de verdad es siempre `features.json`; este resumen no reemplaza su lectura.

## Stack

- Python 3.12 + `uv`.
- FastAPI + Uvicorn.
- SQLAlchemy 2.x + SQLite (`ventas.db`).
- Pydantic v2.
- Jinja2 + Tailwind CSS por CDN + JavaScript vanilla.
- Servidor MCP local + Agente Auditor.
- pytest + httpx.

## Estructura

```text
.agent/                 Reglas y subagentes (builder, verifier)
docs/                   PRD y arquitectura
src/ventas_app/         Código de la aplicación
tests/                  Suite pytest
AGENTS.md               Este archivo
CHECKPOINT.md           Bitácora de sesiones
features.json           Plan atómico F01–F07
init.sh                 Verificación integral del harness
pyproject.toml          uv, dependencias y configuración de pytest
```

## Comandos de ejecución

Todos los comandos se ejecutan desde la raíz del repositorio.

```bash
# Verificación completa del harness (obligatoria antes de cerrar una feature)
./init.sh

# Tests
uv run pytest

# Servidor de desarrollo
uv run uvicorn ventas_app.main:app --reload --port 8000

# Healthcheck
curl http://localhost:8000/health

# Sincronizar dependencias
uv sync

# Agregar una dependencia
uv add <paquete>

# Servidor MCP (disponible desde F06)
uv run python -m ventas_app.mcp_server

# Agente Auditor (disponible desde F07, si se implementa CLI)
uv run python -m ventas_app.auditor
```

> **Prohibido** ejecutar `python`, `python3`, `pytest` o `pip` directamente. Siempre `uv run`.

## Criterio de Done de una feature

1. Implementación y tests dentro del alcance de la feature.
2. `./init.sh` pasa.
3. `uv run pytest` pasa al 100 %.
4. Casos borde probados manualmente por el Verifier.
5. `"passes": true` actualizado solo en la feature verificada.
6. `CHECKPOINT.md` actualizado con sesión, evidencia y próximo paso.
7. Commit claro creado y árbol de trabajo limpio.

## Enlaces rápidos

- Reglas: `.agent/rules.md`
- Builder: `.agent/subagents/builder.md`
- Verifier: `.agent/subagents/verifier.md`
- Especificación: `docs/PRD.md`
- Arquitectura: `docs/ARQUITECTURA.md`
- Bitácora: `CHECKPOINT.md`
- Features: `features.json`
