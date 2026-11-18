# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 08 — UI de Auditoría y Trazabilidad MCP

**Fecha:** 2026-11-17

**Rol ejercido:** Builder + Verifier (fases separadas)

**Feature:** F08

**Estado:** verificada y aprobada

### Objetivo

Cerrar la aplicación con una interfaz de auditoría en vivo y observabilidad de las herramientas MCP, sin alterar la arquitectura del Agente Auditor: cliente MCP real por `stdio`, reglas determinísticas `R1`–`R6`, estados decididos exclusivamente por el backend y enmascaramiento de datos antes del LLM.

### Entregables

#### Resultado estructurado del auditor

- `src/ventas_app/auditor.py`:
  - `ejecutar_auditoria()` y `auditar_ventas()` devuelven un diccionario con:
    - `procesadas`, `aprobadas`, `observadas`.
    - `resumen_llm`, `llm_ok`, `advertencia`.
    - `traza_mcp`: invocaciones ordenadas con `herramienta`, `argumentos` y `estado`.
  - `ClienteMCPStdio` registra cada llamada a `listar_ventas_pendientes`, `obtener_detalle_venta` y `actualizar_estado_venta`, incluyendo errores.
  - `ResultadoLLM` diferencia resumen exitoso, falta de configuración y fallo del proveedor.
  - Se preservan las reglas determinísticas, la idempotencia y la redacción de datos sensibles antes del LLM.

#### API y panel

- `src/ventas_app/routers/api.py`: `POST /api/auditar`, con respuesta validada por `AuditoriaOut` y error controlado ante fallo MCP.
- `src/ventas_app/schemas.py`: `TrazaMCPOut` y `AuditoriaOut`.
- `src/ventas_app/templates/panel.html`:
  - Botón **“Auditar Pendientes con IA”** con estado de carga.
  - Panel colapsable con cantidades, resumen narrativo, advertencia y traza MCP.
  - Columna **Observaciones** con el detalle exacto por venta.
- `src/ventas_app/static/js/auditoria.js`: `POST /api/auditar`, render de la traza y actualización en vivo de badges y observaciones.

#### Documentación y configuración

- `README.md`: endpoint, flujo visual, respuesta y uso de `.env` con Ollama local (`qwen2.5:7b`).
- `.env.example`: variables `OPENAI_*` para un proveedor compatible con OpenAI.
- `docs/PRD.md` y `docs/ARQUITECTURA.md`: contrato del endpoint, UI, trazabilidad y estructura final.
- `features.json`: F08 marcada con `"passes": true`.
- `AGENTS.md`: estado final del proyecto.

#### Tests

- `tests/test_api_auditar.py`: 5 tests del endpoint, con LLM mockeado y servidor MCP real.
- `tests/test_auditor.py`: 76 tests; se agregaron pruebas de resultado estructurado y traza MCP ordenada, incluyendo errores.
- `tests/test_panel.py`: 9 tests; se agregaron controles de auditoría, observaciones exactas y entrega del JavaScript.

### Verificación ejecutada

| Comprobación | Comando / escenario | Resultado |
|---|---|---|
| Harness completo | `./init.sh` | OK |
| Suite de tests | `uv run pytest -v` | `177 passed` |
| Tests de auditor | `uv run pytest tests/test_auditor.py -q` | OK |
| Tests de API de auditoría | `uv run pytest tests/test_api_auditar.py -q` | `5 passed` |
| Tests del panel | `uv run pytest tests/test_panel.py -q` | `9 passed` |
| Endpoint con venta válida | `POST /api/auditar` sobre DB temporal | `1` procesada / `1` aprobada; traza de 3 pasos |
| Endpoint con venta observada | Titular menor de edad | `1` aprobada / `1` observada; `R1` en observaciones |
| Traza MCP | Respuesta JSON | `listar` → `obtener` → `actualizar`; argumentos y estados presentes |
| Actualización del panel | `GET /ventas` posterior a la auditoría | Badges y textos de observaciones visibles |
| Sin ventas pendientes | Segunda corrida | `0` procesadas; solo `listar_ventas_pendientes` |
| LLM no configurado | Sin `OPENAI_API_KEY` | `llm_ok=false`; advertencia de resumen local |
| LLM inalcanzable | `OPENAI_BASE_URL` sin servidor | `ConnectError` informado; auditoría completada y persistida |
| Error MCP | `ejecutar_auditoria` lanza `ErrorMCP` | HTTP `500` con mensaje controlado |
| JavaScript | `node --check src/ventas_app/static/js/auditoria.js` | Sintaxis válida |
| Carga de `.env` | `uv run --env-file .env.example ...` | `qwen2.5:7b` disponible |
| Artefactos | `git status --short` antes del commit | Solo archivos de la feature |

### Decisiones verificadas

- La UI consume el mismo endpoint que usa cualquier cliente HTTP; no duplica reglas ni transiciones.
- La traza MCP se registra en el cliente real, no se reconstruye desde la UI.
- El panel actualiza la tabla usando los argumentos de `actualizar_estado_venta`; no requiere otro endpoint de listado.
- El LLM sigue siendo opcional y solo aporta narrativa; un fallo no bloquea la auditoría.
- `llm_ok=false` y `advertencia` explican tanto la falta de configuración como los errores del proveedor.
- La suite no realiza llamadas externas al LLM; los tests del endpoint lo mockean y el resto de la suite limpia `OPENAI_*`.

### Archivos de la feature

```text
.env.example
README.md
AGENTS.md
CHECKPOINT.md
features.json
docs/PRD.md
docs/ARQUITECTURA.md
src/ventas_app/auditor.py
src/ventas_app/routers/api.py
src/ventas_app/schemas.py
src/ventas_app/templates/panel.html
src/ventas_app/static/js/auditoria.js
tests/test_auditor.py
tests/test_panel.py
tests/test_api_auditar.py
```

### Git

- Commit de cierre: `feat(F08): UI de auditoria en vivo y trazabilidad MCP`.
- Incluye implementación, tests, documentación, configuración de ejemplo, actualización de `features.json` y este checkpoint.

### Próximo paso

El plan F01–F08 está completo. No quedan features pendientes en `features.json`. Mantener la verificación con `./init.sh` y `uv run pytest` ante cualquier cambio futuro.

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
