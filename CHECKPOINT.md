# CHECKPOINT — Bitácora del Harness

> Memoria histórica entre sesiones. Cada feature verificada se registra aquí antes del commit.
> La fuente de verdad del progreso es `features.json`.

---

## Estado actual

- **Última sesión:** Sesión 01 — Inicialización del Harness (2026-11-16).
- **Feature verificada:** F01 — Inicialización del proyecto y healthcheck.
- **Tests:** `1 passed` (`uv run pytest`).
- **Harness:** `./init.sh` OK.
- **Base de datos:** `ventas.db` local generada al iniciar (ignorada por Git).
- **Próxima feature:** **F02** — Modelos SQLAlchemy, schemas Pydantic v2 y seed de planes.
- **Árbol de trabajo esperado:** limpio tras el commit inicial.

---

## Sesión 01 — Inicialización del Harness

**Fecha:** 2026-11-16  
**Rol ejercido:** Builder + Verifier (fases separadas)  
**Feature:** F01  
**Estado:** verificada y aprobada

### Objetivo

Inicializar la infraestructura del harness, el repositorio Git, la documentación funcional/técnica y el esqueleto mínimo verificable de la aplicación, sin implementar las pantallas ni la lógica completa de las tres etapas de venta.

### Entregables

#### Entorno y configuración

- Proyecto `uv` inicializado con Python 3.12 (`pyproject.toml`, `.python-version`, `uv.lock`).
- Dependencias instaladas: FastAPI, Uvicorn, SQLAlchemy, Pydantic, Jinja2, pytest, httpx y MCP.
- Paquete `ventas_app` instalado en modo editable con `uv_build` (`module-name = "ventas_app"`).
- Configuración de pytest:
  - `pythonpath = ["src"]`
  - `testpaths = ["tests"]`
- `.gitignore` para Python, `.venv/`, `__pycache__/`, `*.db`, `.pytest_cache/`, secretos e IDEs.

#### Documentación (`docs/`)

- `docs/PRD.md`: especificación de las 3 etapas, campos obligatorios/opcionales, parentescos, tabla de planes, fórmula de cotización, estados y reglas de auditoría R1–R6.
- `docs/ARQUITECTURA.md`: stack, estructura objetivo, modelo relacional (`planes`, `ventas`, `integrantes`), flujo de estados, API, capa MCP, auditor, testing y trade-offs.

#### Harness y subagentes (`.agent/`)

- `.agent/rules.md`: reglas operativas (uso de `uv run`, una feature por sesión, prohibición de `passes: true` sin verificación, checkpoint + commit al cerrar).
- `.agent/subagents/builder.md`: rol de implementación y reporte al Verifier.
- `.agent/subagents/verifier.md`: rol de QA, verificación, actualización de `features.json`/`CHECKPOINT.md` y commit.

#### Archivos raíz de control

- `AGENTS.md`: punto de entrada, lecturas obligatorias, roles y comandos.
- `features.json`: plan atómico F01–F07. **F01 marcada con `"passes": true`; F02–F07 con `"passes": false`.**
- `CHECKPOINT.md`: este archivo.
- `init.sh`: ejecutable; valida `uv`, archivos/directorios obligatorios y corre `uv run pytest`.
- `README.md`: inicio rápido y enlaces a la documentación.

#### Esqueleto F01 (`src/ventas_app/`)

- `__init__.py`: metadatos del paquete (`__version__ = "0.1.0"`).
- `database.py`:
  - Engine SQLite local en la raíz del proyecto (`ventas.db`), configurable mediante `DATABASE_URL`.
  - `PRAGMA foreign_keys=ON` en cada conexión.
  - `Base` declarativa, `SessionLocal`, `init_db()` y `get_db()`.
- `main.py`:
  - Aplicación FastAPI con `lifespan` que ejecuta `init_db()`.
  - `GET /health` → `{"status": "ok"}`.
- `tests/test_health.py`: valida estado HTTP 200 y cuerpo exacto del healthcheck.

### Estructura creada

```text
APP-HARNESS/
├── .agent/
│   ├── rules.md
│   └── subagents/
│       ├── builder.md
│       └── verifier.md
├── docs/
│   ├── PRD.md
│   └── ARQUITECTURA.md
├── src/
│   └── ventas_app/
│       ├── __init__.py
│       ├── database.py
│       └── main.py
├── tests/
│   └── test_health.py
├── AGENTS.md
├── CHECKPOINT.md
├── README.md
├── features.json
├── init.sh
├── pyproject.toml
├── uv.lock
├── .gitignore
└── .python-version
```

### Verificación ejecutada

| Comprobación | Comando | Resultado |
|---|---|---|
| Suite de tests | `uv run pytest -v` | `1 passed` |
| Harness completo | `./init.sh` | OK (uv, archivos, directorios y tests) |
| Servidor real | `uv run uvicorn ventas_app.main:app --port 8010` | Arranque correcto |
| Healthcheck HTTP | `curl http://127.0.0.1:8010/health` | `{"status":"ok"}` |
| Base SQLite | arranque con `TestClient`/Uvicorn | `ventas.db` creada e ignorada por Git |

### Decisiones técnicas

- Se mantiene `pythonpath = ["src"]` para pytest, tal como exige el harness, y además se instala el paquete en modo editable para que Uvicorn y MCP importen `ventas_app` sin configuración extra.
- La ruta de la base de datos se resuelve desde la raíz del proyecto y admite override por `DATABASE_URL`, facilitando bases temporales en tests futuros.
- `init_db()` se ejecuta en el `lifespan` de FastAPI para que el arranque real y `TestClient` se comporten igual.
- La base queda sin tablas en F01; los modelos y el seed de planes corresponden a F02.
- Los montos se modelarán como enteros ARS y los DNI/códigos postales como texto para preservar ceros iniciales.

### Git

- Commit de cierre: `chore: initialize harness structure and F01 healthcheck`.

### Próximo paso

Ejecutar **F02 — Modelos, schemas y seed de planes**:

1. Leer `docs/PRD.md` (secciones 5–9) y `docs/ARQUITECTURA.md` (secciones 5–8).
2. Implementar `models.py` (`Plan`, `Venta`, `Integrante`), `schemas.py` (Pydantic v2) y el seed idempotente de los 3 planes.
3. Asegurar que `init_db()` cree las tablas y que el seed se ejecute al iniciar la app.
4. Escribir tests de modelos, validadores y seed; ejecutar `./init.sh` y `uv run pytest`.
5. Verificar, marcar F02 con `"passes": true`, actualizar este checkpoint y commitear.
