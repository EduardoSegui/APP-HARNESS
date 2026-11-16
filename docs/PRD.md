# PRD — Aplicación de Carga de Ventas de Obra Social

**Versión:** 1.0  
**Fecha:** 2026-11-16  
**Estado:** Aprobado para implementación incremental  
**Producto:** Wizard web de 3 etapas con validación agéntica vía MCP

---

## 1. Objetivo

Construir una aplicación web local que permita a un operador comercial cargar una venta de obra social en tres etapas consecutivas:

1. Datos del titular y su grupo familiar.
2. Domicilio del titular.
3. Selección de plan, cotización automática y confirmación.

Cada venta confirmada queda en estado `PENDIENTE_VERIFICACION`. Un agente auditor, conectado a la aplicación mediante un servidor MCP local, aplica reglas de negocio sobre los datos persistidos y promueve la venta a `APROBADA` u `OBSERVADA`, dejando trazabilidad de las observaciones.

El producto prioriza la **integridad de los datos**, el **cálculo determinístico del precio** y la **trazabilidad del estado**. No incluye cobros, autenticación ni integración con sistemas externos en esta versión.

---

## 2. Alcance

### 2.1 Incluido

- Wizard web de tres etapas con navegación hacia adelante y hacia atrás.
- Persistencia local en SQLite.
- Carga dinámica de adherentes (alta y baja) dentro de la Etapa 1.
- Cotización automática según plan y cantidad de adherentes.
- Guardado atómico de la venta al finalizar la Etapa 3.
- Listado de ventas con su estado.
- Servidor MCP local con herramientas de consulta y actualización de estado.
- Agente auditor de reglas de negocio.
- Suite de tests automatizados por feature.

### 2.2 Fuera de alcance (v1)

- Autenticación, autorización y multiusuario.
- Pagos, facturación o integración contable.
- Edición o eliminación de ventas confirmadas.
- Reenvío o corrección de ventas `OBSERVADA` desde la interfaz.
- Notificaciones por email o mensajería.
- Despliegue en infraestructura remota.
- Sincronización con sistemas de obra social.
- Historial de auditorías múltiple por venta.

---

## 3. Actores

| Actor | Descripción | Interacción |
|---|---|---|
| Operador comercial | Persona que carga la venta. | Wizard web y panel de ventas. |
| Agente Auditor | Proceso agéntico que valida reglas de negocio. | Servidor MCP local. |
| Sistema | API, base de datos y cálculo de precios. | FastAPI + SQLite. |

---

## 4. Flujo funcional general

```text
Etapa 1: Titular + grupo familiar
        │
        ▼
Etapa 2: Domicilio
        │
        ▼
Etapa 3: Plan + cotización + confirmación
        │
        ▼
Venta persistida atómicamente en PENDIENTE_VERIFICACION
        │
        ▼
Agente Auditor (MCP)
        ├── Todas las reglas OK ──────► APROBADA
        └── Alguna regla falla ───────► OBSERVADA (+ observaciones)
```

La venta se guarda **una sola vez**, al confirmar la Etapa 3. Los pasos anteriores se mantienen en el estado del wizard del navegador y no generan registros parciales en la base de datos.

---

## 5. Etapa 1 — Titular y grupo familiar

### 5.1 Datos del titular

Todos los campos del titular son obligatorios.

| Campo | Tipo | Obligatorio | Regla de validación |
|---|---|---|----|
| `nombre` | Texto | Sí | 2–80 caracteres, sin espacios al inicio/fin. |
| `apellido` | Texto | Sí | 2–80 caracteres, sin espacios al inicio/fin. |
| `dni` | Texto | Sí | 7 u 8 dígitos, sin puntos ni espacios. Único dentro del grupo familiar. |
| `fecha_nacimiento` | Fecha ISO (`YYYY-MM-DD`) | Sí | Fecha válida no futura. El titular debe tener **18 años o más** al momento de la auditoría. |
| `email` | Texto | Sí | Formato de email válido, máximo 254 caracteres. |
| `telefono` | Texto | Sí | 6–25 caracteres; admite dígitos, `+`, espacios, guiones y paréntesis. |

### 5.2 Integrantes / adherentes

La carga es dinámica: el operador puede agregar cero o más integrantes y quitarlos antes de avanzar. Cada integrante es obligatorio en todos sus campos.

| Campo | Tipo | Obligatorio | Regla de validación |
|---|---|---|---|
| `nombre` | Texto | Sí | 2–80 caracteres. |
| `apellido` | Texto | Sí | 2–80 caracteres. |
| `dni` | Texto | Sí | 7 u 8 dígitos. No puede repetirse dentro de la venta, ni coincidir con el DNI del titular. |
| `fecha_nacimiento` | Fecha ISO (`YYYY-MM-DD`) | Sí | Fecha válida no futura. |
| `parentesco` | Enum | Sí | Uno de los valores de la sección 5.3. |

### 5.3 Parentescos permitidos

- `Cónyuge/Pareja`
- `Hijo/a`
- `Nieto/a`
- `Sobrino/a`
- `Familiar a cargo`
- `Amigo/Otro`

El valor se persiste como texto controlado por la aplicación. No se admiten valores fuera de este catálogo.

### 5.4 Reglas de interfaz de la Etapa 1

- Debe existir exactamente un titular.
- El botón **Agregar integrante** añade una fila/tarjeta vacía.
- Cada integrante agregado puede eliminarse antes de continuar.
- Al avanzar, se validan los campos del titular y de todos los integrantes.
- Los errores se muestran junto al campo correspondiente, sin perder los datos cargados.
- La cantidad de adherentes impacta en la cotización de la Etapa 3 y debe reflejarse en el resumen.

---

## 6. Etapa 2 — Domicilio

| Campo | Tipo | Obligatorio | Regla de validación |
|---|---|---|---|
| `calle` | Texto | Sí | 2–120 caracteres. |
| `altura` | Texto | Sí | 1–10 caracteres alfanuméricos; permite `S/N`. |
| `piso_depto` | Texto | No | Máximo 30 caracteres. Puede quedar vacío o `null`. |
| `localidad` | Texto | Sí | 2–80 caracteres. |
| `provincia` | Texto | Sí | 2–80 caracteres. En la UI se ofrece el catálogo de 23 provincias argentinas + Ciudad Autónoma de Buenos Aires. |
| `codigo_postal` | Texto | Sí | Exactamente 4 dígitos (`^[0-9]{4}$`) en v1. Se acepta como texto para preservar ceros iniciales. |

### 6.1 Reglas de interfaz de la Etapa 2

- El botón **Volver** conserva todos los datos de la Etapa 1.
- Al avanzar, se valida el domicilio completo.
- `piso_depto` es el único campo opcional del wizard.

---

## 7. Etapa 3 — Plan, cotización y confirmación

### 7.1 Planes disponibles

Los planes se almacenan en la tabla `planes` de SQLite y se siembran automáticamente al iniciar la aplicación. Los precios están expresados en **pesos argentinos (ARS)** y son enteros.

| Plan | Precio titular (ARS) | Precio por adherente (ARS) |
|---|---:|---:|
| Plan Esencial | 45.000 | 30.000 |
| Plan Integral | 78.000 | 52.000 |
| Plan Superior | 125.000 | 85.000 |

Un adherente es cada integrante cargado en la Etapa 1. El titular no se cuenta como adherente.

### 7.2 Fórmula de cotización

```text
precio_total = precio_titular(plan) + cantidad_adherentes × precio_adherente(plan)
```

Reglas:

- El cálculo se ejecuta **en el servidor** al crear la venta, usando los precios vigentes en la base de datos. Nunca se confía en un total enviado por el cliente.
- El total se persiste en `ventas.precio_total` como una foto del precio al momento de la venta.
- No se aplican descuentos, impuestos ni recargos en v1.
- La interfaz muestra el desglose: precio del titular, cantidad de adherentes, subtotal de adherentes y total.

**Ejemplo:** Plan Integral con 2 adherentes → `78.000 + 2 × 52.000 = 182.000 ARS`.

### 7.3 Confirmación y guardado atómico

Al presionar **Confirmar venta**:

1. Se revalidan todos los datos de las tres etapas.
2. Se verifica que el plan exista y esté activo.
3. Se calcula el `precio_total` en el servidor.
4. Se inserta la venta y todos sus integrantes en **una única transacción**.
5. Si cualquier inserción falla, se hace rollback completo: no quedan ventas ni integrantes parciales.
6. La venta se crea con estado `PENDIENTE_VERIFICACION`, `observaciones = null` y timestamps de creación/actualización.
7. La respuesta incluye el comprobante: número de venta, fecha, titular, plan, cantidad de adherentes, desglose y total.
8. La interfaz muestra el comprobante final y un enlace al panel de ventas.

---

## 8. Estados de la venta

| Estado | Significado |
|---|---|
| `PENDIENTE_VERIFICACION` | Venta confirmada, esperando auditoría. |
| `APROBADA` | La auditoría validó todas las reglas de negocio. |
| `OBSERVADA` | La auditoría detectó una o más reglas incumplidas. |

### 8.1 Transiciones permitidas

```text
PENDIENTE_VERIFICACION ──► APROBADA
PENDIENTE_VERIFICACION ──► OBSERVADA
```

- `APROBADA` y `OBSERVADA` son estados terminales en v1.
- Toda transición a `OBSERVADA` debe incluir al menos una observación.
- Toda transición a `APROBADA` debe limpiar las observaciones previas (deben quedar en `null`).
- No se permite crear una venta directamente en `APROBADA` u `OBSERVADA`.

---

## 9. Reglas de auditoría

El Agente Auditor evalúa las ventas en estado `PENDIENTE_VERIFICACION` y aplica las siguientes reglas:

| ID | Regla | Resultado si falla |
|---|---|---|
| `R1` | El titular tiene **18 años o más** a la fecha de auditoría. | `OBSERVADA` |
| `R2` | Los DNIs del grupo familiar son **únicos** dentro de la venta: no se repite el DNI del titular ni el de ningún integrante. | `OBSERVADA` |
| `R3` | Los **datos obligatorios** de titular, integrantes y domicilio están completos y cumplen formato (nombre, apellido, DNI de 7–8 dígitos, email, teléfono, fechas válidas, parentesco permitido, calle, altura, localidad, provincia). | `OBSERVADA` |
| `R4` | El **código postal** tiene exactamente 4 dígitos. | `OBSERVADA` |
| `R5` | El **plan** existe, está activo y el `precio_total` persistido coincide con el cálculo vigente. | `OBSERVADA` |
| `R6` | La venta posee un titular y todos sus integrantes pertenecen a la misma venta (integridad referencial). | `OBSERVADA` |

### 9.1 Resultado de la auditoría

- Si **todas** las reglas pasan: `estado = APROBADA`, `observaciones = null`.
- Si **alguna** regla falla: `estado = OBSERVADA` y `observaciones` contiene una lista legible con una razón por línea, identificando el campo o integrante afectado.
- La actualización de estado y observaciones se realiza de forma atómica.
- La auditoría es idempotente para ventas ya procesadas: no vuelve a modificar `APROBADA` ni `OBSERVADA` en v1.
- Una venta inexistente no puede auditarse.

### 9.2 Ejemplos de observaciones

```text
R1: El titular tiene 17 años; se requieren 18 o más.
R2: El DNI 30111222 está repetido en el grupo familiar.
R3: Falta el email del titular.
R4: El código postal 'C1425' no tiene el formato de 4 dígitos.
R5: El plan seleccionado no existe o está inactivo.
```

---

## 10. Interfaz web

### 10.1 Wizard

- Ruta principal: `GET /`.
- Tres pasos visibles con indicador de progreso.
- Tecnología: HTML renderizado con Jinja2, Tailwind CSS vía CDN y JavaScript vanilla.
- Persistencia del estado entre pasos en el navegador (objeto JavaScript en memoria y, si se recarga, recuperación desde `sessionStorage`).
- Validación del lado del cliente para UX y validación definitiva del lado del servidor.
- Diseño responsive: escritorio y móvil.
- Al finalizar, pantalla de comprobante con los datos de la venta.

### 10.2 Panel de ventas

- Ruta: `GET /ventas`.
- Lista las ventas de la más reciente a la más antigua.
- Columnas mínimas: ID, titular, plan, cantidad de integrantes, total, estado y observaciones.
- La columna **Observaciones** muestra el motivo exacto de la auditoría:
  - `APROBADA`: “Sin observaciones”.
  - `OBSERVADA`: el texto persistido, una razón `R1`–`R6` por línea.
  - `PENDIENTE_VERIFICACION`: “Pendiente de auditoría”.
- El estado se muestra con un badge de color:
  - `PENDIENTE_VERIFICACION`: ámbar.
  - `APROBADA`: verde.
  - `OBSERVADA`: rojo.
- En la cabecera hay un botón **“Auditar Pendientes con IA”** que ejecuta `POST /api/auditar`.
  - Mientras corre, muestra estado de carga y deshabilita el botón.
  - Al finalizar, despliega un panel colapsable con el resumen numérico, el resumen narrativo del LLM o su advertencia, y la traza ordenada de herramientas MCP.
  - Actualiza en pantalla el estado y las observaciones de las ventas procesadas.
- Estado vacío explícito cuando no hay ventas.
- No se requieren filtros, paginación ni acciones de edición en v1.

---

## 11. API y contrato mínimo

| Método | Ruta | Descripción | Feature |
|---|---|---|---|
| `GET` | `/health` | Healthcheck: `{"status": "ok"}`. | F01 |
| `POST` | `/api/ventas` | Crea una venta completa, calcula el total y devuelve el comprobante. | F03 |
| `GET` | `/api/ventas/{id}` | Devuelve el detalle de una venta con integrantes y plan. | F03 |
| `POST` | `/api/auditar` | Ejecuta el auditor sobre las ventas pendientes y devuelve resultados y traza MCP. | F08 |
| `GET` | `/` | Wizard web de 3 etapas. | F04 |
| `GET` | `/ventas` | Panel HTML de ventas. | F05 |

### 11.1 Reglas de la API

- `POST /api/ventas` recibe titular, domicilio, `plan_id` y la lista de integrantes.
- El cliente **no** envía `precio_total`, `estado` ni `observaciones`; el servidor los determina.
- Error de validación: HTTP `422` con detalle por campo.
- Plan inexistente/inactivo: HTTP `422` o `400` con mensaje claro.
- Venta inexistente en `GET`: HTTP `404`.
- La creación es atómica y devuelve HTTP `201`.
- Los errores no exponen trazas internas ni detalles de SQL.

### 11.2 Contrato de `POST /api/auditar`

La respuesta es un objeto JSON con:

```json
{
  "procesadas": 2,
  "aprobadas": 1,
  "observadas": 1,
  "resumen_llm": "Se aprobó una venta y se observó otra por edad mínima.",
  "llm_ok": true,
  "advertencia": null,
  "traza_mcp": [
    {
      "herramienta": "listar_ventas_pendientes",
      "argumentos": {},
      "estado": "ok"
    },
    {
      "herramienta": "obtener_detalle_venta",
      "argumentos": {"venta_id": 1},
      "estado": "ok"
    },
    {
      "herramienta": "actualizar_estado_venta",
      "argumentos": {"venta_id": 1, "estado": "APROBADA", "observaciones": null},
      "estado": "ok"
    }
  ]
}
```

- `procesadas = aprobadas + observadas`.
- `llm_ok` indica si el resumen narrativo se obtuvo correctamente. Si no hay proveedor configurado o falla, es `false` y `advertencia` explica el motivo.
- `traza_mcp` conserva el orden real de invocaciones al servidor MCP.
- El LLM solo redacta el resumen; las reglas `R1`–`R6` y los estados son determinísticos.

---

## 12. Capa agéntica MCP

### 12.1 Servidor MCP

Servidor local (transporte `stdio`) que expone herramientas sobre la base SQLite de la aplicación:

| Herramienta | Entrada | Salida |
|---|---|---|
| `listar_ventas_pendientes` | — | Lista de ventas `PENDIENTE_VERIFICACION` con id, titular, plan, total y fecha. |
| `obtener_detalle_venta` | `venta_id` | Titular, domicilio, plan, integrantes, total, estado y observaciones. |
| `actualizar_estado_venta` | `venta_id`, `estado` (`APROBADA`/`OBSERVADA`), `observaciones` opcional | Venta actualizada. Valida transiciones y exige observaciones al observar. |

Las herramientas reutilizan la capa de servicios/ORM; no ejecutan SQL concatenado ni aceptan estados arbitrarios.

### 12.2 Agente Auditor

- Se conecta al servidor MCP local por transporte `stdio`.
- Recorre las ventas pendientes.
- Aplica las reglas `R1`–`R6`.
- Actualiza el estado y las observaciones mediante las herramientas MCP, usando la misma lógica de negocio que el servidor.
- Registra un resumen de la ejecución (cantidad de aprobadas y observadas).
- No modifica ventas ya procesadas.
- Es ejecutable de forma local y repetible.
- Opcionalmente puede generar un resumen narrativo con un proveedor compatible
  con OpenAI. El LLM no decide estados ni reemplaza las reglas; si falla o no
  responde, la auditoría continúa con el resumen local.
- Devuelve un resultado estructurado con cantidades, estado del LLM y
  `traza_mcp`: la secuencia ordenada de herramientas invocadas, sus argumentos y
  su estado (`ok`/`error`). Esta traza alimenta el panel de auditoría en vivo.

---

## 13. Requisitos no funcionales

| Categoría | Requisito |
|---|---|
| Persistencia | SQLite local (`ventas.db`), ignorado por Git. |
| Integridad | Transacciones atómicas; claves foráneas activas; restricciones de unicidad. |
| Rendimiento | Respuestas locales < 300 ms para operaciones CRUD simples. |
| Seguridad | Validación server-side, ORM parametrizado, sin secretos en el repositorio. |
| Usabilidad | Wizard claro, errores junto al campo, navegación sin pérdida de datos. |
| Accesibilidad | Labels asociados, foco visible, contraste razonable, navegación por teclado. |
| Testing | `uv run pytest` debe pasar al 100 % antes de cerrar una feature. |
| Operación | Arranque documentado con `uv`; healthcheck disponible. |
| Idiomas | Interfaz y mensajes en español. |

---

## 14. Criterios de aceptación globales

1. El wizard permite completar las 3 etapas y confirmar una venta.
2. Los adherentes se agregan y eliminan dinámicamente.
3. El total se calcula en el servidor con la tabla de precios y se persiste.
4. La venta y sus integrantes se guardan en una sola transacción.
5. Toda venta nueva queda en `PENDIENTE_VERIFICACION`.
6. El panel lista las ventas con estado, titular, plan y total.
7. El servidor MCP expone las tres herramientas y valida sus entradas.
8. El auditor aplica las reglas y actualiza el estado con observaciones.
9. El panel permite lanzar la auditoría, muestra el resumen del LLM y la traza MCP, y expone las observaciones exactas por venta.
10. `./init.sh` y `uv run pytest` pasan antes de marcar cualquier feature como completada.
11. Cada feature cerrada queda registrada en `CHECKPOINT.md` y en un commit de Git.

---

## 15. Plan de features

| Feature | Alcance |
|---|---|
| F01 | Estructura inicial, SQLite y `GET /health`. |
| F02 | Modelos SQLAlchemy, esquemas Pydantic v2 y seed de planes. |
| F03 | `POST /api/ventas` y `GET /api/ventas/{id}` con cálculo de total. |
| F04 | Wizard web de 3 etapas con persistencia y adherentes dinámicos. |
| F05 | Panel `GET /ventas`. |
| F06 | Servidor MCP con las tres herramientas. |
| F07 | Agente Auditor y reglas de negocio. |
| F08 | UI de auditoría en vivo, endpoint `POST /api/auditar` y trazabilidad MCP. |
