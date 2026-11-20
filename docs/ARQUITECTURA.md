# ARQUITECTURA — Aplicación de Ventas de Obra Social

**Versión:** 1.0  
**Fecha:** 2026-11-16  
**Stack:** Python 3.12 · uv · FastAPI · SQLAlchemy 2.x · SQLite · Pydantic v2 · Jinja2 · Tailwind CDN · MCP

---

## 1. Visión general

La aplicación se organiza en cinco capas con dependencias unidireccionales:

```text
┌────────────────────────────────────────────────────────────┐
│  Presentación   Jinja2 + Tailwind CDN + JS vanilla         │
├────────────────────────────────────────────────────────────┤
│  API HTTP       FastAPI (routers + validación Pydantic)    │
├────────────────────────────────────────────────────────────┤
│  Dominio        Servicios de precio, estados y auditoría   │
├────────────────────────────────────────────────────────────┤
│  Persistencia   SQLAlchemy ORM + SQLite (ventas.db)        │
├────────────────────────────────────────────────────────────┤
│  Capa agéntica  Servidor MCP + Agente Auditor              │
└────────────────────────────────────────────────────────────┘
```

Principios:

- **Una única fuente de verdad:** la base SQLite. El wizard y el auditor leen/escriben a través de la API o de servicios compartidos, nunca mediante SQL ad-hoc.
- **El servidor manda:** validaciones, cálculo de precios, estados y observaciones se determinan en el backend.
- **Transacciones atómicas:** una venta y sus integrantes se confirman juntos o no se confirman.
- **Simplicidad operativa:** aplicación local, sin contenedores ni servicios externos obligatorios.
- **Trazabilidad:** cada venta conserva estado, observaciones y timestamps.

---

## 2. Stack y dependencias

| Componente | Versión / elección | Uso |
|---|---|---|
| Python | 3.12 | Runtime. |
| uv | 0.12.x | Gestión de entorno, dependencias y ejecución. |
| FastAPI | 0.163.x | API HTTP y aplicación web. |
| Uvicorn | 0.54.x | Servidor ASGI local. |
| SQLAlchemy | 2.1.x | ORM y transacciones. |
| SQLite | 3.x (stdlib) | Persistencia local en `ventas.db`. |
| Pydantic | 2.14.x | Schemas y validación. |
| Jinja2 | 3.1.x | Templates HTML server-side. |
| Tailwind CSS | CDN | Estilos del wizard y del panel. |
| MCP SDK | 2.3.x | Servidor de herramientas para el agente. |
| pytest / httpx | 9.x / 0.28.x | Tests y cliente HTTP. |

`pyproject.toml` configura `[tool.pytest.ini_options] pythonpath = ["src"]`, y además el proyecto se instala en modo editable con `uv_build` (`module-name = "ventas_app"`). Esto permite ejecutar tests, Uvicorn y el servidor MCP sin manipular `PYTHONPATH`.

---

## 3. Estructura del repositorio

### 3.1 Estado actual

La estructura actual coincide con la estructura objetivo de 3.2. El estado vigente y el próximo paso están en `STATE.md`; la fuente de verdad del progreso es `features.json` y la historia de las sesiones está en `CHECKPOINT.md` (ventana reciente) y `docs/journal/` (archivo).

### 3.2 Estructura del repositorio

Los archivos marcados con una feature se incorporan en esa etapa. La organización es indicativa; se permite dividir routers o servicios adicionales siempre que se respeten las capas.

```text
raíz del repositorio
├── AGENTS.md                    # punto de entrada y router de contexto
├── STATE.md                     # estado actual generado
├── CHECKPOINT.md                # ventana de las últimas 2 sesiones
├── features.json                # índice y progreso de features
├── features/                    # packets autocontenidos (F11)
├── scripts/contexto.py          # estado, rotación y presupuesto
├── docs/
│   ├── journal/2026.md          # archivo histórico de sesiones
│   └── INDEX.md                 # mapa de documentación
└── .opencode/commands/sesion.md # comando /sesion

src/ventas_app/
├── __init__.py
├── main.py                      # App FastAPI, lifespan, routers, health
├── database.py                  # Engine SQLite, SessionLocal, Base, get_db
├── models.py                    # F02: Plan, Venta, Integrante
├── schemas.py                   # F02/F08: schemas Pydantic v2
├── seed.py                      # F02: seed idempotente de planes
├── services/
│   ├── __init__.py
│   ├── ventas.py                # F03: creación atómica y consulta
│   ├── pricing.py               # F03: cálculo de precio_total
│   ├── eventos.py               # F18: linaje de ventas
│   └── estados.py               # F06/F07: transiciones válidas
├── routers/
│   ├── __init__.py
│   ├── api.py                   # F03/F08: /api/ventas y /api/auditar
│   └── web.py                   # F04/F05: /, /ventas
├── templates/
│   ├── base.html                # F04
│   ├── wizard.html              # F04/F15: alta y edición
│   ├── comprobante.html         # F04
│   ├── panel.html               # F05/F08/F15/F18: panel, filtros y acciones
│   ├── legajo.html              # F15/F18: ficha y línea de tiempo
│   └── credencial.html          # F18: credencial provisoria
├── static/
│   ├── js/wizard.js             # F04: estado, adherentes, fetch
│   └── js/auditoria.js          # F08: auditoría en vivo y traza MCP
├── mcp_server.py                # F06: herramientas MCP
└── auditor.py                   # F07/F08: reglas, resultado y traza MCP

tests/
├── conftest.py                  # Fixtures de DB temporal y cliente
├── test_health.py               # F01
├── test_models.py               # F02
├── test_api_ventas.py           # F03
├── test_wizard.py               # F04
├── test_panel.py                # F05/F08
├── test_mcp_server.py           # F06
├── test_auditor.py              # F07/F08
└── test_api_auditar.py          # F08
```

---

## 4. Configuración y arranque

### 4.1 Base de datos

```python
# src/ventas_app/database.py (comportamiento)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{RUTA_RAIZ / 'ventas.db'}")
```

- Por defecto, `ventas.db` se crea en la raíz del repositorio (ignorado por Git).
- `DATABASE_URL` permite usar una base temporal en tests (`sqlite:///./tmp/test.db`) sin tocar la base de desarrollo.
- `connect_args={"check_same_thread": False}` es necesario para el acceso desde el threadpool de FastAPI/TestClient.
- Las sesiones se crean con `sessionmaker(bind=engine, autoflush=False, autocommit=False)`.
- `get_db()` es la dependencia FastAPI que garantiza el cierre de cada sesión.

### 4.2 Comandos

```bash
./init.sh                                              # Verificación del harness
uv run pytest                                          # Suite de tests
uv run uvicorn ventas_app.main:app --reload --port 8000
uv run python -m ventas_app.mcp_server                 # F06
uv run python -m ventas_app.auditor                    # F07 (si se implementa CLI)
```

- `GET /health` responde `{"status": "ok"}` y se usa como smoke test.
- El wizard estará en `http://localhost:8000/`.
- El panel estará en `http://localhost:8000/ventas`.

---

## 5. Modelo relacional

### 5.1 Diagrama

```text
┌──────────────────────┐
│        planes        │
├──────────────────────┤
│ id            PK     │
│ nombre        UNIQUE │
│ precio_titular       │
│ precio_adherente     │
│ activo               │
└──────────┬───────────┘
           │ 1
           │
           │ N
┌──────────▼───────────┐          ┌──────────────────────────┐
│        ventas        │ 1      N │       integrantes        │
├──────────────────────┤──────────├──────────────────────────┤
│ id            PK     │          │ id                PK     │
│ nombre_titular       │          │ venta_id          FK     │
│ apellido_titular     │          │ nombre                   │
│ dni_titular          │          │ apellido                 │
│ fecha_nac_titular    │          │ dni                      │
│ email                │          │ fecha_nacimiento         │
│ telefono             │          │ parentesco               │
│ calle                │          └──────────────────────────┘
│ altura               │
│ piso_depto (nullable)│          UNIQUE (venta_id, dni)
│ localidad            │          FK venta_id ON DELETE CASCADE
│ provincia            │
│ codigo_postal        │
│ plan_id       FK     │
│ precio_total         │
│ estado               │
│ observaciones (null) │
│ creado_en            │
│ actualizado_en       │
└──────────────────────┘
```

### 5.2 Tabla `planes`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | Integer | PK, autoincrement. |
| `nombre` | String(50) | NOT NULL, UNIQUE. |
| `precio_titular` | Integer | NOT NULL, > 0. Pesos ARS. |
| `precio_adherente` | Integer | NOT NULL, >= 0. Pesos ARS. |
| `activo` | Boolean | NOT NULL, default `true`. |

Seed idempotente al iniciar la app:

| nombre | precio_titular | precio_adherente |
|---|---:|---:|
| Plan Esencial | 45000 | 30000 |
| Plan Integral | 78000 | 52000 |
| Plan Superior | 125000 | 85000 |

El seed inserta solo los planes faltantes (por `nombre`) y no pisa precios editados manualmente.

### 5.3 Tabla `ventas`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | Integer | PK, autoincrement. |
| `nombre_titular` | String(80) | NOT NULL. |
| `apellido_titular` | String(80) | NOT NULL. |
| `dni_titular` | String(8) | NOT NULL, indexado. La unicidad se valida dentro de la venta (no global). |
| `fecha_nacimiento_titular` | Date | NOT NULL. |
| `email` | String(254) | NOT NULL. |
| `telefono` | String(25) | NOT NULL. |
| `calle` | String(120) | NOT NULL. |
| `altura` | String(10) | NOT NULL. |
| `piso_depto` | String(30) | NULL. |
| `localidad` | String(80) | NOT NULL. |
| `provincia` | String(80) | NOT NULL. |
| `codigo_postal` | String(4) | NOT NULL. |
| `plan_id` | Integer | FK `planes.id`, NOT NULL. |
| `medio_pago` | String(30) | NOT NULL, default `PAGO_FACIL`, CHECK contra el catálogo. |
| `subtotal_base` | Integer | NOT NULL, >= 0. Precio de lista antes del descuento. |
| `descuento_porcentaje` | Integer | NOT NULL, >= 0. 30, 20 o 0 según el medio de pago. |
| `pago_titular` | String(80) | NULL. Titular de tarjeta o cuenta. |
| `pago_marca_entidad` | String(80) | NULL. Marca de tarjeta o entidad bancaria. |
| `pago_ultimos_4` | String(4) | NULL. Últimos 4 dígitos; nunca PAN/CBU completo. |
| `pago_vencimiento` | String(5) | NULL. `MM/AA` de tarjeta. |
| `pago_cuil` | String(11) | NULL. CUIL/CUIT declarado para CBU. |
| `regimen_afiliacion` | String(30) | NOT NULL, default `PARTICULAR`. F17. |
| `cuil_titular` | String(11) | NULL. Obligatorio para desregulados. F17. |
| `aporte_estimado` | Integer | NOT NULL, default 0. F17. |
| `ddjj_completada` | Boolean | NOT NULL, default false. Distingue “sin declarar” de “sin riesgos”. F16. |
| `ddjj_preexistencias` | Boolean | NOT NULL, default false. F16. |
| `ddjj_internaciones` | Boolean | NOT NULL, default false. F16. |
| `ddjj_embarazo` | Boolean | NOT NULL, default false. F16. |
| `ddjj_medicacion_cronica` | Boolean | NOT NULL, default false. F16. |
| `ddjj_discapacidad` | Boolean | NOT NULL, default false. F16. |
| `ddjj_detalle` | Text | NULL. Detalle declarado de salud. F16. |
| `precio_total` | Integer | NOT NULL, >= 0. Total neto a pagar; puede ser 0 si el aporte cubre la base. |
| `estado` | String(30) | NOT NULL, default `PENDIENTE_VERIFICACION`, CHECK en los 3 estados. |
| `observaciones` | Text | NULL. |
| `creado_en` | DateTime | NOT NULL, default UTC now. |
| `actualizado_en` | DateTime | NOT NULL, on update UTC now. |

Índices: `ix_ventas_estado`, `ix_ventas_dni_titular`.

Las bases creadas antes de F13 se actualizan al arrancar mediante una migración SQLite idempotente en `database.py`: agrega las tres columnas nuevas y completa las filas históricas con `medio_pago='PAGO_FACIL'`, `subtotal_base=precio_total` y `descuento_porcentaje=0`.

F14 agrega las cinco columnas `pago_*` (NULL para filas históricas), F16 las columnas `ddjj_*` (indicadores false, `ddjj_completada=false`, detalle NULL) y F17 `regimen_afiliacion` (default `PARTICULAR`), `cuil_titular` (NULL) y `aporte_estimado` (0). F17 también reconstruye la tabla si el CHECK histórico `precio_total > 0` impide un total cero, conservando filas, índices y claves foráneas; los `integrantes` se respaldan y reinsertan porque `DROP TABLE ventas` dispara el `ON DELETE CASCADE`. La misma migración es idempotente y se ejecuta en `init_db()` y al arrancar el servidor MCP.

No se impone unicidad global de DNI: la regla de negocio exige unicidad **dentro del grupo familiar de una venta**, no entre ventas distintas.

### 5.4 Tabla `integrantes`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | Integer | PK, autoincrement. |
| `venta_id` | Integer | FK `ventas.id` ON DELETE CASCADE, NOT NULL, indexado. |
| `nombre` | String(80) | NOT NULL. |
| `apellido` | String(80) | NOT NULL. |
| `dni` | String(8) | NOT NULL. |
| `fecha_nacimiento` | Date | NOT NULL. |
| `parentesco` | String(30) | NOT NULL, CHECK contra el catálogo. |

Restricción: `UNIQUE (venta_id, dni)` para impedir duplicados a nivel de base. La comparación contra el DNI del titular se resuelve en la capa de dominio/auditoría.

### 5.5 Integridad

- SQLite debe ejecutar `PRAGMA foreign_keys=ON` por conexión (event listener de SQLAlchemy).
- Borrar una venta elimina sus integrantes (`CASCADE`). La UI no expone borrado en v1.
- Los estados y parentescos se validan en Pydantic y, cuando sea posible, con `CHECK` en la base.
- Montos en enteros para evitar errores de punto flotante.

### 5.6 Tabla `venta_eventos` (F18)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | Integer | PK, autoincrement. |
| `venta_id` | Integer | FK `ventas.id` ON DELETE CASCADE, NOT NULL, indexado. |
| `tipo` | String(30) | NOT NULL: `CREADA`, `EDITADA`, `AUDITADA_APROBADA`, `AUDITADA_OBSERVADA`. |
| `estado_anterior` | String(30) | NULL. |
| `estado_nuevo` | String(30) | NULL. |
| `detalle` | Text | NULL. Resumen del hito, sin datos sensibles. |
| `actor` | String(30) | NOT NULL: `operador` o `auditor`. |
| `creado_en` | DateTime | NOT NULL, default UTC now. |

Los eventos son inmutables y se registran dentro de la misma transacción que la mutación de la venta. Se indexan por `venta_id` y `creado_en` para la línea de tiempo.

---

## 6. Flujo de estados

```text
                    POST /api/ventas (transacción)
                              │
                              ▼
                 ┌───────────────────────────┐
                 │ PENDIENTE_VERIFICACION    │
                 └─────────────┬─────────────┘
                               │
                    Agente Auditor / MCP
                    (actualizar_estado_venta)
                               │
              ┌────────────────┴────────────────┐
              │ todas las reglas OK             │ alguna regla falla
              ▼                                 ▼
     ┌─────────────────┐              ┌─────────────────┐
     │    APROBADA     │              │    OBSERVADA    │
     │ observaciones:  │              │ observaciones:  │
     │ null            │              │ texto requerido │
     └─────────────────┘              └─────────────────┘
           (terminal v1)                  (terminal v1)
```

Reglas de transición:

| Origen | Destino permitido | Condición |
|---|---|---|
| `PENDIENTE_VERIFICACION` | `APROBADA` | Todas las reglas de auditoría pasan. |
| `PENDIENTE_VERIFICACION` | `OBSERVADA` | Al menos una regla falla; observaciones no vacías. |
| `PENDIENTE_VERIFICACION` | `PENDIENTE_VERIFICACION` | Edición del legajo en F15; se limpian observaciones. |
| `OBSERVADA` | `PENDIENTE_VERIFICACION` | Edición/subsanación en F15; se limpian observaciones. |
| `APROBADA` | — | Terminal e inmutable. |

La validación de transiciones de auditoría se centraliza en `services/estados.py` y se reutiliza tanto en la API como en MCP y en el auditor. La edición de F15 se valida en el servicio de ventas y devuelve `409` si la venta está aprobada. Una transición inválida no modifica la fila.

---

## 7. Creación atómica de una venta (F03)

`POST /api/ventas` ejecuta el siguiente algoritmo:

```text
1. Validar payload con Pydantic (titular, domicilio, plan_id, medio_pago, instrumento, DDJJ, régimen e integrantes).
2. Abrir sesión SQLAlchemy.
3. BEGIN implícito.
4. Buscar plan por id y verificar activo=True.
5. Normalizar datos (trim, DNI sin puntos).
6. Validar que los DNIs del payload sean únicos (titular + integrantes).
7. Validar el instrumento de pago y derivar solo metadatos enmascarados; descartar PAN/CVV.
8. Calcular subtotal_base con precios leídos de la fila del plan.
9. Aplicar descuento half-up y aporte estimado; calcular precio_total neto.
10. Crear Venta con estado=PENDIENTE_VERIFICACION, desglose, DDJJ y observaciones=null.
11. flush() para obtener venta.id.
12. Crear Integrante para cada adherente con venta_id.
13. Registrar evento CREADA en `venta_eventos` (misma transacción).
14. commit().
15. Refrescar y devolver el comprobante (HTTP 201).

Si cualquier paso 4–13 falla:
    rollback()
    devolver error controlado (400/422/500), sin filas parciales.
```

El payload del cliente incluye `medio_pago`, `tarjeta`/`cbu` cuando corresponde, DDJJ de salud, régimen, CUIL y `aporte_estimado`. No incluye `pago_*`, `subtotal_base`, `descuento_porcentaje`, `base_bonificada`, `precio_total`, `estado`, `observaciones`, `id` ni timestamps. Si los envía, se rechazan por configuración de Pydantic (`extra="forbid"`).

`PUT /api/ventas/{id}` (F15) reutiliza el mismo algoritmo, elimina los integrantes anteriores y crea los nuevos dentro de la transacción. Si la venta está `APROBADA`, devuelve `409` antes de modificar nada. Las ediciones registran `EDITADA`; las transiciones MCP registran `AUDITADA_APROBADA` o `AUDITADA_OBSERVADA` en la misma transacción.

---

## 8. Capa API

### 8.1 Endpoints

| Método | Ruta | Feature | Respuesta |
|---|---|---|---|
| `GET` | `/health` | F01 | `{"status": "ok"}` |
| `POST` | `/api/ventas` | F03 | `201` + comprobante completo. |
| `GET` | `/api/ventas` | F18 | `200` + página filtrada de ventas. |
| `GET` | `/api/ventas/{id}` | F03 | `200` + detalle; `404` si no existe. |
| `GET` | `/api/ventas/{id}/eventos` | F18 | `200` + linaje; `404` si no existe. |
| `PUT` | `/api/ventas/{id}` | F15 | `200` + legajo actualizado; `404`/`409`/`422`. |
| `POST` | `/api/auditar` | F08 | `200` + resultado estructurado y traza MCP. |
| `GET` | `/api/metricas` | F19 | KPIs y distribuciones en JSON. |
| `GET` | `/api/exportar/padron` | F19 | CSV/JSON del padrón aprobado. |
| `GET` | `/api/exportar/cobranzas` | F19 | CSV/JSON del lote de cobranzas. |
| `GET` | `/` | F04 | HTML wizard. |
| `GET` | `/ventas` | F05/F08/F18 | HTML panel con auditoría, búsqueda y filtros. |
| `GET` | `/ventas/{id}` | F15/F18 | Ficha de legajo en lectura; F18 agrega línea de tiempo. |
| `GET` | `/ventas/{id}/editar` | F15 | Wizard en modo edición. |
| `GET` | `/ventas/{id}/credencial` | F18 | Credencial provisoria de aprobada. |
| `GET` | `/dashboard` | F19 | Tablero ejecutivo. |

Se podrá agregar `GET /api/planes` como apoyo del wizard (no obligatorio), devolviendo los planes activos.

### 8.1.1 Resultado de auditoría

`POST /api/auditar` devuelve:

- `procesadas`, `aprobadas`, `observadas`.
- `resumen_llm`, `llm_ok`, `advertencia`.
- `traza_mcp`: lista ordenada de objetos con `herramienta`, `argumentos` y `estado`.

La traza se produce en el cliente MCP real y no reemplaza las observaciones persistidas. El endpoint es síncrono respecto de la corrida: responde cuando terminan todas las invocaciones MCP y la eventual llamada al LLM.

### 8.2 Manejo de errores

- `422 Unprocessable Entity`: validación Pydantic; se devuelve detalle por campo.
- `400 Bad Request`: regla de negocio violada (por ejemplo, plan inactivo).
- `404 Not Found`: recurso inexistente.
- `409 Conflict`: transición de estado inválida (MCP/auditoría).
- `500 Internal Server Error`: error inesperado; mensaje genérico, detalle solo en logs.

### 8.3 Schemas Pydantic v2

- `IntegranteIn`: nombre, apellido, dni, fecha_nacimiento, parentesco.
- `TarjetaIn`: marca, número, titular, vencimiento, CVV. El CVV no se persiste.
- `CbuIn`: número, entidad, titular, CUIL.
- `SaludIn`: indicadores de DDJJ, detalle y `declaracion_confirmada` obligatoria.
- `VentaIn`: titular + domicilio + `plan_id` + `medio_pago` + `tarjeta`/`cbu` condicional + DDJJ + régimen + `integrantes`.
- `VentaUpdateIn`: misma estructura, con instrumento opcional para conservar metadatos enmascarados si el medio no cambia.
- `VentaOut`: datos persistidos + `plan` + `medio_pago` + desglose + `pago_*` enmascarados + DDJJ + régimen + integrantes + estado + observaciones + timestamps.
- `MetricasOut` y `DistribucionOut`: agregados de F19.
- `PlanOut`: id, nombre, precios, activo.
- Validadores reutilizables para DNI, teléfono, código postal, email, tarjeta, CBU, CUIL y vencimiento.
- `model_config = ConfigDict(extra="forbid", from_attributes=True)` en los schemas de entrada/salida correspondientes.
- Los schemas de salida nunca incluyen PAN completo, CBU completo ni CVV.

---

## 9. Interfaz web (F04 / F05)

### 9.1 Wizard

- `GET /` renderiza `wizard.html` con el catálogo de planes y parentescos.
- El estado del wizard vive en un objeto JS:
  ```js
  {
    titular: {...},
    integrantes: [...],
    domicilio: {...},
    plan_id: null,
    medio_pago: null,
    salud: {...},
    regimen: {...}
  }
  ```
- Se sincroniza en `sessionStorage` para tolerar recargas accidentales. Los números completos de tarjeta/CBU y el CVV **no** se guardan en `sessionStorage`.
- Navegación: Paso 1 → Paso 2 → Paso 3 → Confirmación. En modo edición (F15), la navegación es libre entre las tres etapas.
- **Adherentes dinámicos:** agregar crea un objeto con ID temporal; eliminar lo quita del array y del DOM; el contador se actualiza.
- La Etapa 3 exige elegir un plan y un medio de pago. Si el medio es tarjeta/CBU, muestra el subformulario de instrumento (F14). La cotización se calcula en el cliente como vista previa, con el mismo redondeo half-up del backend. Al confirmar, se envía el payload a `POST /api/ventas` (o `PUT` en edición) y se usa el total devuelto por el servidor.
- La Etapa 1 incorpora la DDJJ de salud (F16/F20) con respuestas Sí/No explícitas y descripción condicional; la Etapa 3 incorpora régimen, CUIL y aporte (F17).
- El comprobante final muestra ID, fecha, titular, plan, medio de pago, instrumento enmascarado, adherentes, subtotal, descuento, aporte, total y estado inicial.
- Tailwind se carga por CDN; no hay build de frontend.

### 9.2 Panel

- `GET /ventas` consulta las ventas con `joinedload` del plan y conteo de integrantes; F18 agrega filtros por texto, estado, plan, medio de pago y régimen, con paginación.
- Tabla responsive con columna de **Medio de pago** e instrumento enmascarado, total bonificado, badges de estado y una columna de **Observaciones** que muestra el texto persistido o el estado de la auditoría.
- F15 agrega **Ver / Editar legajo** para pendientes/observadas; F18 agrega ficha con línea de tiempo y credencial provisoria para aprobadas.
- F19 agrega el enlace al tablero `/dashboard` y exportaciones CSV/JSON.
- Botón **“Auditar Pendientes con IA”** en la cabecera:
  - Hace `POST /api/auditar` y bloquea el botón mientras corre.
  - Muestra un panel colapsable con `procesadas`/`aprobadas`/`observadas`, el resumen del LLM, su advertencia si corresponde y la tabla de `traza_mcp`.
  - Actualiza en el DOM el badge y las observaciones de cada venta procesada usando los argumentos de `actualizar_estado_venta` de la traza.
  - Si la petición falla, muestra un mensaje controlado sin romper la tabla.
- El JavaScript se carga desde `static/js/auditoria.js`; no hay build de frontend.

---

## 10. Capa agéntica

### 10.1 Servidor MCP (F06)

- Archivo: `src/ventas_app/mcp_server.py`.
- Transporte: `stdio` (no abre puertos).
- Implementación con el SDK oficial `mcp` (FastMCP o API de bajo nivel, según la versión instalada).
- Herramientas:
  - `listar_ventas_pendientes()`
  - `obtener_detalle_venta(venta_id: int)`
  - `actualizar_estado_venta(venta_id: int, estado: Literal["APROBADA", "OBSERVADA"], observaciones: str | None = None)`
- Cada herramienta abre una sesión propia (`SessionLocal`) y la cierra en `finally`.
- Reutiliza `services/estados.py`; no duplica reglas de transición.
- Devuelve diccionarios serializables JSON, con fechas en ISO 8601.
- Errores: venta inexistente, estado inválido, observaciones faltantes al observar.

### 10.2 Agente Auditor (F07)

- Archivo: `src/ventas_app/auditor.py`.
- Se ejecuta como **cliente MCP real** por transporte `stdio`: lanza el servidor local (`python -m ventas_app.mcp_server`) mediante `mcp.client.stdio`.
- Flujo:
  ```text
  conectar cliente MCP
  ventas = listar_ventas_pendientes()
  para cada venta:
      detalle = obtener_detalle_venta(id)
      errores = aplicar_reglas(detalle)   # R1–R8
      si errores:
          actualizar_estado_venta(id, "OBSERVADA", "\n".join(errores))
      else:
          actualizar_estado_venta(id, "APROBADA", None)
  imprimir resumen
  ```
- El auditor no importa `SessionLocal` ni consulta los modelos ORM directamente: toda lectura y escritura de ventas pasa por las herramientas MCP.
- Devuelve un diccionario estructurado con:
  - `procesadas`, `aprobadas`, `observadas`.
  - `resumen_llm`, `llm_ok`, `advertencia`.
  - `traza_mcp`: invocaciones ordenadas (`herramienta`, `argumentos`, `estado`).
- El cliente `ClienteMCPStdio` registra cada llamada a `listar_ventas_pendientes`, `obtener_detalle_venta` y `actualizar_estado_venta`, incluyendo las que terminan en error.
- Las reglas se implementan como funciones puras que reciben el detalle y
  devuelven una lista de strings. Esto facilita tests unitarios sin base de
  datos.
- R5 valida que el plan esté activo, que el medio de pago sea válido, que el
  instrumento de tarjeta/CBU esté completo y que `subtotal_base`,
  `descuento_porcentaje`, `aporte_estimado` y `precio_total` coincidan con la
  cotización vigente, usando el mismo redondeo half-up que el backend.
- R7 exige `ddjj_completada`, valida el detalle cuando hay indicadores y deriva a revisión médica los casos declarados de preexistencias, internaciones o discapacidad.
- R8 valida régimen de afiliación, CUIL y aporte estimado.
- Fecha de referencia inyectable (`hoy: date | None`) para tests determinísticos
  de edad.
- El auditor comparte la capa de servicios con el servidor MCP a través del
  protocolo, de modo que ambos aplican las mismas validaciones.
- Opcionalmente puede usar un proveedor compatible con OpenAI para redactar un
  resumen narrativo de la corrida:
  - `OPENAI_API_KEY`: habilita el resumen. Sin esta variable no se llama al LLM.
  - `OPENAI_BASE_URL`: URL base alternativa (por ejemplo, Ollama).
  - `OPENAI_MODEL`: modelo a utilizar.
  - `OPENAI_TIMEOUT`: timeout de la llamada.
  - El LLM **no decide estados**: las reglas R1–R8 son la fuente de verdad.
  - Timeout, error HTTP o respuesta inválida se informan como advertencia y se
    usa el resumen local; la auditoría continúa.
- No modifica ventas que no estén en `PENDIENTE_VERIFICACION`.

### 10.3 Separación de responsabilidades

| Componente | Responsabilidad |
|---|---|
| API | Recibir y validar la venta; calcular y persistir. |
| Servidor MCP | Exponer operaciones controladas a un agente externo. |
| Auditor | Decidir el resultado aplicando reglas de negocio. |
| Servicios | Centralizar transacciones y transiciones. |
| Modelos | Persistencia y restricciones estructurales. |

El auditor se ejecuta como cliente MCP por `stdio` para mantener una única vía de acceso a las ventas. La lógica de reglas queda del lado del agente y las transiciones se delegan al servidor, que reutiliza la capa de servicios.

---

## 11. Testing

### 11.1 Estrategia

| Nivel | Alcance | Herramientas |
|---|---|---|
| Unitario | Validadores, cálculo de precios, reglas de auditoría, transiciones. | pytest |
| Integración API | Endpoints con base SQLite temporal y `TestClient`. | pytest + httpx |
| Integración API de auditoría | `POST /api/auditar` con LLM mockeado, estados persistidos y `traza_mcp`. | pytest + TestClient |
| Integración web | Render de templates y presencia de campos clave. | pytest + TestClient |
| MCP | Invocación directa de las funciones de herramienta. | pytest |
| End-to-end ligero | Flujo crear → listar → auditar. | pytest |

### 11.2 Fixtures previstas

- `db_temporal`: crea un engine SQLite en archivo temporal o en memoria con `StaticPool`, ejecuta `Base.metadata.create_all` y aplica el seed; la inyecta mediante `app.dependency_overrides[get_db]`.
- `client`: `TestClient(app)` con la dependencia de DB sobrescrita.
- `plan_esencial`, `venta_pendiente`: datos de prueba reutilizables.

### 11.3 Reglas

- Ninguna feature se marca completada sin tests nuevos y `uv run pytest` al 100 %.
- Los tests no dependen del orden de ejecución ni de la base de desarrollo.
- No se usan sleeps ni llamadas de red.
- La fecha actual se inyecta en las reglas que dependen de edad.

---

## 12. Harness de desarrollo

### 12.1 Roles

| Rol | Archivo | Responsabilidad |
|---|---|---|
| Builder | `.agent/subagents/builder.md` | Implementa la siguiente feature pendiente y sus tests. |
| Verifier / QA | `.agent/subagents/verifier.md` | Ejecuta `./init.sh` + tests, valida casos borde, marca `passes`, registra el cierre y commitea. |

### 12.2 Memoria en capas

El harness separa la información por vida útil para no precargar todo en cada sesión:

| Capa | Archivo | Cuándo se lee |
|---|---|---|
| Invariantes y comandos | `AGENTS.md` | Siempre (auto-cargado por OpenCode). |
| Protocolo de sesión | `.agent/rules.md` | Al iniciar y cerrar. |
| Estado actual | `STATE.md` | Siempre; es generado, no se edita a mano. |
| Ficha de la feature pendiente | `features/F0X.md` | Solo la feature pendiente. |
| Historia | `docs/journal/` | Bajo demanda (`grep`), nunca completa. |
| Especificación | `docs/PRD.md`, `docs/ARQUITECTURA.md` | Solo las secciones citadas por la ficha. |
| Rol activo | `.agent/subagents/*.md` | Solo Builder o Verifier. |

`CHECKPOINT.md` es una ventana de las últimas 2 sesiones; `scripts/contexto.py rotate` mueve las anteriores a `docs/journal/`. `STATE.md` se genera desde `features.json` y la última entrada de la bitácora.

### 12.3 Ciclo por feature

```text
1. Leer AGENTS.md (auto), STATE.md y el rol activo.
2. Identificar la primera feature con passes=false en features.json.
3. Leer solo su ficha features/F0X.md y las secciones citadas de docs/.
4. Si no existe la ficha, planificar antes de construir.
5. Builder implementa la feature y sus tests.
6. Builder ejecuta uv run pytest y ./init.sh.
7. Verifier ejecuta ./init.sh y uv run pytest, y prueba casos borde.
8. Verifier verifica los criterios de aceptación de la ficha.
9. Verifier marca passes=true solo en esa feature.
10. Verifier agrega una entrada compacta a CHECKPOINT.md, rota la bitácora,
    regenera STATE.md y ejecuta ./init.sh.
11. Verifier commitea y confirma git status limpio.
12. Siguiente sesión: STATE.md indica la próxima feature o que hace falta planificar.
```

### 12.4 Presupuesto de contexto

`uv run python scripts/contexto.py --check` se ejecuta dentro de `./init.sh` y falla si un archivo always-on excede su cap:

| Archivo | Cap |
|---|---:|
| `AGENTS.md` | 6 KB |
| `.agent/rules.md` | 4 KB |
| `STATE.md` | 3 KB |
| `CHECKPOINT.md` | 12 KB y ≤2 sesiones |
| Roles (`builder.md`, `verifier.md`) | 3 KB cada uno |
| Packet de feature | 8 KB |

Si un archivo crece, se recorta o se archiva; no se ignora el fallo.

### 12.5 Invariantes

- Nunca se trabaja en más de una feature por sesión.
- Nunca se marca `passes=true` sin verificación completa.
- `STATE.md` es la foto actual; `features.json` es la verdad del progreso; el historial no se precarga.
- Un hecho se guarda en un solo lugar canónico; los demás documentos enlazan.
- Los cambios de alcance se reflejan primero en `docs/` y `features.json`.

### 12.6 Planificación e intake

Cuando `features.json` no tiene features pendientes, la sesión es de planificación, no de construcción:

1. Leer solo las secciones del PRD/ARQ relacionadas con el tema.
2. Copiar `features/_TEMPLATE.md` a `features/F0X.md` y completar objetivo, alcance, fuera de alcance, criterios de aceptación, archivos, tests y referencias.
3. Agregar la feature a `features.json` con `passes: false` y `packet: features/F0X.md`.
4. Regenerar `STATE.md` y ejecutar `contexto.py --check`.
5. Commitear solo documentación (`docs(plan): F0X — ...`).

No se escribe código hasta que la ficha exista y esté commiteada. El Builder no debe inferir alcance desde `features.json`: la descripción es un índice; la ficha es la orden de trabajo.

---

## 13. Decisiones y trade-offs

| Decisión | Motivo | Trade-off |
|---|---|---|
| SQLite local | Simplicidad, cero servicios externos, suficiente para un operador. | Un solo escritor; no apto para alta concurrencia. |
| Tailwind por CDN | Evita build de frontend y mantiene el foco en el backend. | Requiere internet para estilos; sin purge. |
| Wizard con JS vanilla | Menor complejidad; sin framework SPA. | Estado manual y más código imperativo. |
| Precio calculado en servidor | Seguridad e integridad. | El cliente necesita un round-trip para el total final. |
| Estados terminales en v1 | Evita flujos de corrección no especificados. | Una venta observada no se puede corregir en esta versión. |
| Seed idempotente | Arranque repetible sin duplicados. | Cambios de precio manuales no se sobreescriben. |
| MCP por stdio | No expone superficie de red. | El cliente debe lanzar el proceso. |
| Auditoría vía MCP | Una única vía de acceso y reutilización real de las herramientas. | Requiere lanzar el servidor MCP como subproceso. |
| LLM solo para resumen | Se conserva el resultado determinístico de las reglas. | La narración depende de un proveedor externo opcional. |

---

## 14. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Concurrencia de escritura SQLite | Bloqueos o `database is locked`. | Transacciones cortas, timeout y WAL si es necesario. |
| Diferencias de API entre versiones del SDK MCP | F06 puede requerir ajustes. | Aislar el servidor detrás de funciones de servicio testeables. |
| Validación de email sin dependencia extra | Uso de regex en lugar de `EmailStr`. | Regex conservador + tests; agregar `email-validator` solo si se adopta `EmailStr`. |
| Fechas y zonas horarias | Edad calculada de forma inconsistente. | Fechas de nacimiento como `Date`; cálculo con `date.today()` inyectable. |
| Tailwind CDN no disponible | Interfaz sin estilos. | Estructura HTML semántica; estilos críticos mínimos inline si hace falta. |
| Datos parciales en fallos | Ventas incompletas. | Una transacción por creación; rollback explícito. |
| DNI con ceros iniciales | Pérdida de datos. | Persistir DNI y código postal como texto. |

---

## 15. Roadmap técnico

| Feature | Entregable | Tests esperados |
|---|---|---|
| F01 | Estructura, SQLite, `/health`. | `test_health.py`. |
| F02 | Modelos, schemas y seed de planes. | Creación de tablas, seed idempotente, validadores. |
| F03 | API de ventas y cálculo de total. | Altas válidas, totales por plan, validaciones, atomicidad, 404. |
| F04 | Wizard de 3 etapas. | Render, campos, JS de adherentes, flujo de confirmación. |
| F05 | Panel de ventas. | Render de filas, badges de estado, estado vacío. |
| F06 | Servidor MCP. | Listar pendientes, detalle, transiciones válidas e inválidas. |
| F07 | Agente Auditor. | Reglas R1–R6, edad límite, DNI duplicado, CP inválido, idempotencia. |
| F08 | UI de auditoría en vivo y trazabilidad MCP. | Endpoint con LLM mockeado, respuesta estructurada, traza ordenada, panel y observaciones. |
| F09 | Contexto always-on y estado del harness. | `AGENTS.md`/reglas/roles livianos, `STATE.md` generado, checker de presupuestos. |
| F10 | Bitácora rotativa, caps y comando `/sesion`. | Rotación de `CHECKPOINT.md`, journal, caps en `init.sh`, comando de OpenCode. |
| F11 | Feature packets e intake. | Plantilla, packets autocontenidos y protocolo de planificación. |
| F12 | Rediseño visual del wizard y el panel. | Render, estados y pruebas visuales existentes. |
| F13 | Medios de pago y descuentos. | Cotización, desglose, API, wizard, panel, comprobante, migración y R5. |
| F14 | Instrumentos de tarjeta/CBU enmascarados. | Validación, persistencia enmascarada, UI condicional, R5 y migración. |
| F15 | Edición multi-etapa de ventas. | `PUT`, precarga, recálculo, rollback, 409 en aprobadas y tests de UI. |
| F16 | DDJJ de salud y R7. | Migración, validaciones, R7 y privacidad. |
| F17 | Régimen, CUIL y aportes. | Pricing neto, migración, R8 y tests de API/UI. |
| F18 | Búsqueda, filtros, linaje y credencial. | `VentaEvento`, filtros, ficha, timeline y credencial. |
| F19 | Tablero y exportaciones. | Métricas SQL, CSV/JSON, filtros y privacidad. |

---

## 16. Estado del proyecto

El estado vigente y el próximo paso están en `STATE.md`. Este documento describe el diseño estable y no mantiene una copia del estado; la historia de las sesiones está en `CHECKPOINT.md` y `docs/journal/`.
