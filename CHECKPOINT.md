# CHECKPOINT — Bitácora del Harness

> Memoria histórica entre sesiones. Cada feature verificada se registra aquí antes del commit.
> La fuente de verdad del progreso es `features.json`.

---

## Estado actual

- **Última sesión:** Sesión 04 — Wizard web de 3 etapas (2026-11-16).
- **Feature verificada:** F04 — Wizard web de 3 etapas.
- **Tests:** `70 passed` (`uv run pytest -v`).
- **Harness:** `./init.sh` OK.
- **Base de datos:** `ventas.db` local generada al iniciar (ignorada por Git); tests aislados en SQLite temporal.
- **Próxima feature:** **F05** — Panel de ventas.
- **Árbol de trabajo esperado:** limpio tras el commit de cierre de F04.

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

---

## Sesión 02 — Modelos, schemas y seed de planes

**Fecha:** 2026-11-16

**Rol ejercido:** Builder + Verifier (fases separadas)

**Feature:** F02

**Estado:** verificada y aprobada

### Objetivo

Implementar la capa de persistencia y validación de F02: modelos SQLAlchemy (`Plan`, `Venta`, `Integrante`), schemas Pydantic v2 y seed automático e idempotente de los tres planes al iniciar la aplicación.

### Entregables

#### Modelos (`src/ventas_app/models.py`)

- `EstadoVenta` y `Parentesco` como enums de dominio.
- `Plan`: nombre único, `precio_titular > 0`, `precio_adherente >= 0`, `activo` por defecto.
- `Venta`:
  - Datos completos del titular y domicilio.
  - `plan_id` FK, `precio_total > 0`, estado con CHECK de los 3 valores.
  - `observaciones`, timestamps UTC, índices de estado y DNI.
- `Integrante`:
  - FK `venta_id` con `ON DELETE CASCADE`.
  - `UNIQUE (venta_id, dni)`.
  - CHECK de parentesco contra el catálogo del PRD.
- Relaciones bidireccionales `Plan.ventas`, `Venta.integrantes`.

#### Schemas (`src/ventas_app/schemas.py`)

- `IntegranteIn` y `VentaIn` con `extra="forbid"`.
- `PlanOut`, `IntegranteOut` y `VentaOut` con `from_attributes=True`.
- Validación de nombres, DNI, email, teléfono, altura, código postal y fechas no futuras.
- Normalización de espacios y de `piso_depto` vacío a `None`.
- Validación de DNIs únicos en el grupo familiar (titular + adherentes).

#### Seed (`src/ventas_app/seed.py`)

- `PLANES_SEED` con los precios del PRD.
- `seed_planes()` idempotente por nombre: inserta faltantes y no sobreescribe precios existentes.
- Ejecución automática desde el `lifespan` de FastAPI.

#### Integración y tests

- `init_db()` importa los modelos antes de `create_all`.
- `main.py` crea el esquema y ejecuta el seed al iniciar.
- `tests/conftest.py` aísla toda la suite en una SQLite temporal, con limpieza por test.
- `tests/test_models.py`, `tests/test_schemas.py` y `tests/test_seed.py`.

### Verificación ejecutada

| Comprobación | Comando / escenario | Resultado |
|---|---|---|
| Harness completo | `./init.sh` | OK |
| Suite de tests | `uv run pytest -v` | `41 passed` |
| Tablas | `init_db()` + `inspect(engine)` | `planes`, `ventas`, `integrantes` |
| Healthcheck | `TestClient` → `GET /health` | `200` + `{"status":"ok"}` |
| Seed al iniciar | dos arranques consecutivos de `TestClient(app)` | 3 planes, sin duplicados |
| Precios | consulta ORM | Esencial 45.000/30.000; Integral 78.000/52.000; Superior 125.000/85.000 |
| Schema válido | `VentaIn` con 1 adherente | OK; `piso_depto` vacío → `None` |
| Casos inválidos | DNI duplicado, CP `C1043`, fecha futura, campo extra, email inválido | Rechazados con `ValidationError` |
| Persistencia | venta + 2 integrantes | Estado `PENDIENTE_VERIFICACION`, relaciones y timestamps OK |
| DNI duplicado | dos integrantes con el mismo DNI | `IntegrityError` por `UNIQUE (venta_id, dni)` |
| Parentesco inválido | valor `Hija` fuera del catálogo | `IntegrityError` por CHECK |
| Cascada | eliminar venta | integrantes eliminados |
| Artefactos | `git ls-files '*.db' '*.pyc' '.env'` | sin resultados |

### Decisiones verificadas

- `VentaIn` usa campos planos (`nombre_titular`, etc.) alineados con el modelo; F03/F04 deben respetar ese contrato.
- La edad mínima del titular no se valida en el schema: corresponde a la regla R1 del auditor (F07).
- El email se valida con regex propio, sin agregar `email-validator`.
- `seed_planes()` hace commit propio y está pensado para el arranque; no se anida en otras transacciones.
- SQLite no conserva tzinfo en `DateTime(timezone=True)`; los timestamps se generan en UTC.

### Archivos de la feature

```text
src/ventas_app/models.py
src/ventas_app/schemas.py
src/ventas_app/seed.py
src/ventas_app/database.py
src/ventas_app/main.py
tests/conftest.py
tests/test_models.py
tests/test_schemas.py
tests/test_seed.py
```

### Git

- Implementación base: `b3c43df` — `F02: Modelos, schemas y seed de planes` (ya en `origin/main`).
- Commit de cierre de verificación: `chore(F02): mark feature verified and update checkpoint`.

### Próximo paso

Ejecutar **F03 — API REST de ventas y cotización**:

1. Implementar `POST /api/ventas` y `GET /api/ventas/{id}`.
2. Recibir `VentaIn`, verificar que el plan exista y esté activo, y calcular `precio_total` en el servidor con los precios de la base.
3. Persistir venta e integrantes en una única transacción, con estado inicial `PENDIENTE_VERIFICACION`.
4. Devolver `201` con `VentaOut` y `404` para ventas inexistentes.
5. Escribir tests de cálculo por plan, validaciones, atomicidad y errores; ejecutar `./init.sh` y `uv run pytest`.
6. Verificar, marcar F03 con `"passes": true`, actualizar este checkpoint y commitear.

---

## Sesión 03 — API REST de ventas y cotización

**Fecha:** 2026-11-16

**Rol ejercido:** Builder + Verifier (fases separadas)

**Feature:** F03

**Estado:** verificada y aprobada

### Objetivo

Implementar la API REST mínima para crear y consultar ventas, con validación de entrada, verificación del plan, cálculo automático de `precio_total` en el servidor y persistencia atómica de la venta y sus integrantes.

### Entregables

#### Servicios

- `src/ventas_app/services/pricing.py`:
  - `calcular_precio_total(plan, cantidad_adherentes)`.
  - Fórmula: `precio_titular + cantidad × precio_adherente`.
  - Rechaza cantidades negativas.
- `src/ventas_app/services/ventas.py`:
  - `crear_venta(db, datos)`: busca el plan, exige `activo=True`, calcula el total, crea venta e integrantes y hace un único `commit`.
  - Rollback explícito ante cualquier fallo de persistencia.
  - `obtener_venta(db, venta_id)` con `joinedload(plan)` y `selectinload(integrantes)`.
  - Excepciones de dominio `PlanNoDisponibleError` y `VentaNoEncontradaError`.

#### Router y endpoints

- `src/ventas_app/routers/api.py`:
  - `POST /api/ventas` → `201` con `VentaOut`.
  - `GET /api/ventas/{venta_id}` → `200` con detalle o `404`.
  - Plan inexistente o inactivo → `400`.
- `src/ventas_app/main.py`: registro del router en la app FastAPI.

#### Tests

- `tests/test_pricing.py`: 6 casos de cálculo y cantidad negativa.
- `tests/test_api_ventas.py`: 18 tests de integración HTTP.
- `tests/conftest.py`: fixture `client` con `TestClient` y lifespan/seed.

### Verificación ejecutada

| Comprobación | Comando / escenario | Resultado |
|---|---|---|
| Harness completo | `./init.sh` | OK |
| Suite de tests | `uv run pytest -v` | `65 passed` |
| Servidor real | Uvicorn con SQLite temporal | inicio correcto |
| Healthcheck real | `GET /health` | `200` + `{"status":"ok"}` |
| Alta válida | `POST /api/ventas` Plan Integral + 2 adherentes | `201`, total `182.000` |
| Consulta | `GET /api/ventas/{id}` | `200`, plan e integrantes |
| Venta inexistente | `GET /api/ventas/999999` | `404` |
| CP inválido | `POST /api/ventas` | `422` |
| Total impuesto por cliente | `precio_total` en el payload | `422` |
| Plan inexistente | `POST /api/ventas` | `400` |
| Plan inactivo | `POST /api/ventas` | `400` |
| Precios vigentes | modificación de precios en DB y alta | total recalculado (`120.000`) |
| Persistencia real | consulta posterior | 2 ventas y 4 integrantes |
| Atomicidad | fallo de commit simulado | sin venta ni integrantes parciales |
| Artefactos | `git ls-files '*.db' '*.pyc' '.env'` | sin resultados |

### Casos borde verificados

- Totales para los 3 planes, incluyendo ventas sin adherentes.
- `precio_total`, `estado` y `observaciones` enviados por el cliente → `422`.
- DNI duplicado en el grupo familiar y código postal inválido → `422`.
- `plan_id=0` → `422`.
- Plan inactivo o inexistente → `400`.
- Venta inexistente → `404`.
- Fallo de commit → rollback total.

### Decisiones verificadas

- El contrato de entrada mantiene campos planos (`nombre_titular`, `calle`, etc.) definidos en F02.
- El total se calcula exclusivamente en el servidor con los precios de la base.
- Los errores de plan no disponible se devuelven como `400`, permitido por el PRD.
- `GET` precarga plan e integrantes para evitar consultas perezosas durante la serialización.
- `VentaOut.plan` muestra los precios actuales del plan; `precio_total` es la foto al momento de la venta.
- No se agregó `GET /api/planes` ni lógica de wizard/panel/MCP/auditor.

### Archivos de la feature

```text
src/ventas_app/services/__init__.py
src/ventas_app/services/pricing.py
src/ventas_app/services/ventas.py
src/ventas_app/routers/__init__.py
src/ventas_app/routers/api.py
src/ventas_app/main.py
tests/conftest.py
tests/test_pricing.py
tests/test_api_ventas.py
```

### Git

- Commit de cierre: `feat(F03): API REST de ventas y cotización`.
- Incluye implementación, tests, actualización de `features.json` y este checkpoint.

### Próximo paso

Ejecutar **F04 — Wizard web de 3 etapas**:

1. Implementar `GET /` con Jinja2 y Tailwind CDN.
2. Construir el wizard de titular/adherentes, domicilio y plan/cotización con persistencia entre pasos.
3. Agregar alta/baja dinámica de adherentes y resumen final con comprobante.
4. Consumir `POST /api/ventas` respetando el contrato plano de F03.
5. Escribir tests de render y flujo; ejecutar `./init.sh` y `uv run pytest`.
6. Verificar, marcar F04 con `"passes": true`, actualizar este checkpoint y commitear.

---

## Sesión 04 — Wizard web de 3 etapas

**Fecha:** 2026-11-16

**Rol ejercido:** Builder + Verifier (fases separadas)

**Feature:** F04

**Estado:** verificada y aprobada

### Objetivo

Implementar la interfaz web de carga de ventas en tres etapas, con estado persistente en el navegador, adherentes dinámicos, vista previa de cotización y comprobante final generado a partir de la respuesta del servidor.

### Entregables

#### Rutas y assets

- `src/ventas_app/routers/web.py`:
  - `GET /` consulta los planes activos y renderiza el wizard.
  - Catálogo de 24 jurisdicciones argentinas para el domicilio.
  - Filtro Jinja `pesos` para mostrar montos con formato argentino.
- `src/ventas_app/main.py`: registro del router web y montaje de `/static`.

#### Templates

- `src/ventas_app/templates/base.html`: layout común, Tailwind CDN, header y footer.
- `src/ventas_app/templates/wizard.html`:
  - Indicador de progreso de 3 etapas.
  - Paso 1: titular y tarjetas dinámicas de adherentes.
  - Paso 2: domicilio con `piso_depto` opcional.
  - Paso 3: planes, cotización y confirmación.
- `src/ventas_app/templates/comprobante.html`: comprobante con ID, fecha, titular, plan, adherentes, desglose, total y estado.

#### JavaScript

- `src/ventas_app/static/js/wizard.js`:
  - Estado con titular, integrantes, domicilio, plan y paso actual.
  - Persistencia en `sessionStorage`.
  - Alta/baja dinámica de adherentes con ID temporal.
  - Validación inline de campos, DNI único, fechas no futuras, CP y plan.
  - Vista previa de cotización calculada en cliente.
  - Envío del payload plano a `POST /api/ventas`.
  - Visualización del comprobante usando el total devuelto por el servidor.
  - Manejo de errores 400/422 y de red.

#### Tests

- `tests/test_wizard.py`: 5 tests de render, planes activos/inactivos, estado sin planes, assets JS e idempotencia del seed.

### Verificación ejecutada

| Comprobación | Comando / escenario | Resultado |
|---|---|---|
| Harness completo | `./init.sh` | OK |
| Suite de tests | `uv run pytest -v` | `70 passed` |
| Render inicial | `GET /` | `200`, HTML con 3 pasos, 3 planes y JS cargado |
| Asset JS | `GET /static/js/wizard.js` | `200`, `text/javascript` |
| Validación inicial | Avanzar con todo vacío | Permanece en paso 1 con errores |
| Flujo feliz | Plan Integral + 1 adherente | Total `130.000`, comprobante `#1` |
| Persistencia | Recarga en paso 2 | Paso, titular y adherente conservados |
| Adherentes | Agregar 2 y eliminar 1 | Contador y cotización actualizados |
| API real | `GET /api/ventas/1` | Total `130000`, estado `PENDIENTE_VERIFICACION` |
| DNI duplicado | Titular y adherente con el mismo DNI | Bloqueado en paso 1 |
| CP inválido | `123` | Bloqueado en paso 2 |
| Sin adherentes | Plan Esencial + `piso_depto` vacío | Total `45.000`; `piso_depto=null` persistido |
| Plan inactivo | Desactivar plan con la página abierta | `400` mostrado en UI; sin venta adicional |
| Planes inactivos | Test de render | Excluidos del wizard |
| Sin planes activos | Test de render | Aviso visible y sin radios |
| Excepciones JS | Flujos de navegador | Ninguna |
| Artefactos | `git ls-files '*.db' '*.pyc' '.env'` | Sin resultados versionados |

### Decisiones verificadas

- El wizard obtiene los planes activos directamente en `GET /`; no se agregó `GET /api/planes`.
- La cotización del cliente es solo una vista previa. El total persistido y mostrado en el comprobante proviene del servidor.
- El payload enviado mantiene el contrato plano de F03 y no incluye `precio_total`, `estado` ni `observaciones`.
- El `_id` temporal de los adherentes queda solo en el estado del navegador.
- `piso_depto` vacío se envía como `null`.
- El enlace al panel de ventas se difiere a F05, cuando exista `GET /ventas`.
- Tailwind se mantiene por CDN, sin build de frontend, conforme a la arquitectura.

### Archivos de la feature

```text
src/ventas_app/routers/web.py
src/ventas_app/main.py
src/ventas_app/templates/base.html
src/ventas_app/templates/wizard.html
src/ventas_app/templates/comprobante.html
src/ventas_app/static/js/wizard.js
tests/test_wizard.py
```

### Git

- Commit de cierre: `feat(F04): wizard web de 3 etapas`.
- Incluye implementación, tests, actualización de `features.json` y este checkpoint.

### Próximo paso

Ejecutar **F05 — Panel de ventas**:

1. Implementar `GET /ventas` con listado de ventas, plan y cantidad de integrantes.
2. Mostrar titular, plan, total y badge de estado (`PENDIENTE_VERIFICACION`, `APROBADA`, `OBSERVADA`).
3. Mantener el panel como solo lectura, sin acciones de escritura.
4. Agregar el enlace al panel desde el comprobante si el alcance de F05 lo permite.
5. Escribir tests de render/listado; ejecutar `./init.sh` y `uv run pytest`.
6. Verificar, marcar F05 con `"passes": true`, actualizar este checkpoint y commitear.
