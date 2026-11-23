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

- SSO/LDAP/OAuth; la autenticación local y el RBAC se incorporan en F23.
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

### 5.5 Declaración jurada de salud (F16)

El alta incorpora una DDJJ familiar con cinco preguntas de respuesta explícita **Sí/No**: preexistencias, internaciones en los últimos 12 meses, embarazo, medicación crónica y discapacidad declarada. Si alguna respuesta es “Sí”, el campo de descripción es obligatorio; si todas son “No”, se puede continuar sin descripción. El usuario debe confirmar explícitamente la declaración. Se persiste `ddjj_completada` y los indicadores; R7 deriva a revisión médica los casos que correspondan. No se adjuntan estudios ni se muestra el detalle en el listado general.

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
subtotal_base = precio_titular(plan) + cantidad_adherentes × precio_adherente(plan)
descuento_porcentaje = según medio de pago
descuento_monto = round_half_up(subtotal_base × descuento_porcentaje / 100)
base_bonificada = subtotal_base - descuento_monto
precio_total = max(0, base_bonificada - aporte_estimado)
```

`aporte_estimado` es 0 para particulares y un monto declarado para desregulados (F17).

Medios de pago y descuentos:

| Medio de pago | Descuento |
|---|---:|
| Tarjeta de crédito | 30% |
| CBU / Débito automático | 20% |
| Pago Fácil / Rapipago / Oficinas | 0% |
| Cobrador a domicilio | 0% |

Reglas:

- El cálculo se ejecuta **en el servidor** al crear la venta, usando los precios vigentes en la base de datos. Nunca se confía en un total enviado por el cliente.
- `medio_pago` es obligatorio en la Etapa 3 y en `POST /api/ventas`.
- Se persisten `subtotal_base`, `descuento_porcentaje` y `precio_total` como una foto de la cotización al momento de la venta.
- El redondeo es half-up (0,5 hacia arriba) y se aplica con aritmética entera para que el backend y la vista previa del wizard coincidan.
- No se aplican impuestos ni recargos en v1.
- La interfaz muestra el desglose: precio del titular, cantidad de adherentes, subtotal base, descuento y total a pagar.

**Ejemplo:** Plan Integral con 2 adherentes → `78.000 + 2 × 52.000 = 182.000 ARS`. Con tarjeta de crédito: `182.000 − 54.600 = 127.400 ARS`.

### 7.3 Confirmación y guardado atómico

Al presionar **Confirmar venta**:

1. Se revalidan todos los datos de las tres etapas.
2. Se verifica que el plan exista y esté activo.
3. Se validan el medio de pago, la DDJJ, el régimen y el aporte; se calculan `subtotal_base`, `descuento_porcentaje`, `aporte_estimado` y `precio_total` en el servidor.
4. Se inserta la venta y todos sus integrantes en **una única transacción**.
5. Si cualquier inserción falla, se hace rollback completo: no quedan ventas ni integrantes parciales.
6. La venta se crea con estado `PENDIENTE_VERIFICACION`, `observaciones = null` y timestamps de creación/actualización.
7. La respuesta incluye el comprobante: número de venta, fecha, titular, plan, cantidad de adherentes, desglose, instrumento enmascarado y total.
8. La interfaz muestra el comprobante final y un enlace al panel de ventas.

### 7.4 Instrumento de pago (F14)

Cuando el medio es `TARJETA_CREDITO` o `CBU`, el alta exige datos del instrumento:

| Tarjeta | CBU |
|---|---|
| Marca (VISA, MASTERCARD, AMEX, CABAL) | Entidad bancaria |
| Número de 16 dígitos | Número de 22 dígitos |
| Titular de la tarjeta | Titular de la cuenta |
| Vencimiento `MM/AA` futuro | CUIL/CUIT de 11 dígitos |
| CVV de 3 o 4 dígitos | — |

Reglas de seguridad y persistencia:

- El número completo y el CVV **nunca** se persisten; el CVV solo se valida en memoria.
- Se guardan `pago_titular`, `pago_marca_entidad`, `pago_ultimos_4`, `pago_vencimiento` y `pago_cuil`.
- La API rechaza con `422` un instrumento faltante, inválido o incoherente con el medio de pago.
- Pago Fácil y Cobrador no requieren datos bancarios.
- Comprobante y panel muestran solo el instrumento enmascarado (`VISA •••• 4242`, `Banco X · CBU •••• 8901`).
- Los datos son ficticios en desarrollo; no hay cobro, débito ni integración bancaria real.

### 7.5 Régimen y aportes (F17)

El régimen `PARTICULAR` paga la base bonificada. Los regímenes `RELACION_DEPENDENCIA` y `MONOTRIBUTO` requieren CUIL y permiten declarar un `aporte_estimado`:

```text
base_bonificada = subtotal_base - descuento_monto
precio_total = max(0, base_bonificada - aporte_estimado)
```

El aporte es declarativo en v1; no se integra con ANSES/ARCA. R8 valida la coherencia del régimen, CUIL y aporte. Si el aporte cubre toda la base, el total puede ser `0`; la migración F17 relaja el CHECK histórico sin perder filas.

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
OBSERVADA ──► PENDIENTE_VERIFICACION   (edición/subsanación en F15)
PENDIENTE_VERIFICACION ──► PENDIENTE_VERIFICACION (edición en F15)
```

- `APROBADA` es terminal e inmutable.
- `OBSERVADA` deja de ser terminal a partir de F15: puede corregirse y volver a pendiente.
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
| `R5` | El **plan** existe, está activo, el **medio de pago** es válido, el instrumento de tarjeta/CBU está completo y el desglose persistido (`subtotal_base`, `descuento_porcentaje`, `aporte_estimado` y `precio_total`) coincide con el cálculo vigente con redondeo half-up. | `OBSERVADA` |
| `R6` | La venta posee un titular y todos sus integrantes pertenecen a la misma venta (integridad referencial). | `OBSERVADA` |
| `R7` | La **DDJJ de salud** está completa; los casos con preexistencias, internaciones o discapacidad declarada se derivan a revisión médica. | `OBSERVADA` |
| `R8` | El **régimen de afiliación**, CUIL y aporte estimado son coherentes: desregulado exige CUIL, particular exige aporte 0 y el aporte no supera la base bonificada. | `OBSERVADA` |

### 9.1 Resultado de la auditoría

- Si **todas** las reglas pasan: `estado = APROBADA`, `observaciones = null`.
- Si **alguna** regla falla: `estado = OBSERVADA` y `observaciones` contiene una lista legible con una razón por línea, identificando el campo o integrante afectado.
- La actualización de estado y observaciones se realiza de forma atómica.
- La auditoría es idempotente para ventas ya procesadas: no vuelve a modificar `APROBADA` ni `OBSERVADA` sin una edición previa.
- Una venta inexistente no puede auditarse.

### 9.2 Ejemplos de observaciones

```text
R1: El titular tiene 17 años; se requieren 18 o más.
R2: El DNI 30111222 está repetido en el grupo familiar.
R3: Falta el email del titular.
R4: El código postal 'C1425' no tiene el formato de 4 dígitos.
R5: El plan seleccionado no existe o está inactivo.
R5: El subtotal base persistido (100000) no coincide con el cálculo vigente (130000).
R5: El descuento persistido (0%) no coincide con el medio de pago 'TARJETA_CREDITO' (30%).
R5: Faltan los datos enmascarados de la tarjeta de crédito.
R7: La DDJJ de salud declara preexistencias y requiere revisión médica.
R8: El régimen RELACION_DEPENDENCIA exige CUIL del titular.
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
- La Etapa 3 incluye la selección obligatoria de medio de pago, con badges de descuento y actualización en vivo del subtotal, descuento y total.
- Si el medio es tarjeta o CBU, se despliega el subformulario de instrumento con validación de formatos; el CVV y el número completo no se persisten.
- La Etapa 1 incorpora la DDJJ de salud (F16): panel de respuestas Sí/No obligatorias, descripción condicional y confirmación expresa. La Etapa 3 incorpora régimen, CUIL y aportes (F17).
- Al finalizar, pantalla de comprobante con los datos de la venta, medio de pago, instrumento enmascarado, subtotal, descuento, aporte y total a pagar.
- F15 agrega el modo edición del wizard para ventas pendientes u observadas, con navegación libre entre etapas.
- F21 unifica el rail y el resumen en una columna sticky y permite navegar libremente por las tres etapas en alta y edición. Cada etapa muestra check verde si sus obligatorios están completos; la validación completa se ejecuta al confirmar.
- El checkbox de confirmación de la DDJJ es un control estándar alineado con su etiqueta.

### 10.2 Panel de ventas

- Ruta: `GET /ventas`.
- Lista las ventas de la más reciente a la más antigua.
- Columnas mínimas: ID, titular, plan, cantidad de integrantes, medio de pago, régimen, total bonificado, aporte, estado y observaciones.
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
- F15 agrega la acción **Editar legajo** para ventas pendientes u observadas y **Ver legajo** en modo lectura para aprobadas.
- F18 agrega buscador por DNI/nombre/apellido, filtros por estado, plan, medio de pago y régimen, y paginación de 20 resultados.
- La ficha del legajo muestra el desglose, adherentes, DDJJ resumida, régimen y una **línea de tiempo** inmutable de creación, edición y auditoría.
- Las ventas aprobadas tienen **Credencial provisoria** imprimible, sin datos de salud ni instrumentos de pago.
- F19 agrega un tablero ejecutivo en `/dashboard` con KPIs y exportaciones CSV/JSON de padrón y cobranzas.

### 10.3 Tablero ejecutivo

- Ruta: `GET /dashboard`, con filtros de fecha (`desde`, `hasta`) y plan.
- KPIs: ventas por estado, tasa de aprobación/observación, titulares y adherentes cubiertos, MRR bruto, descuentos, aportes, recaudación neta y tickets promedio.
- F22 separa los KPIs en embudo/auditoría/cobertura y finanzas; las distribuciones muestran porcentaje y barra de proporción.
- Los motivos `R1`–`R8` se muestran en grilla compacta de dos columnas, atenuando las reglas sin incidencias.
- El tablero agrega filtro **Estado** y las exportaciones respetan `desde`, `hasta`, `plan_id` y `estado`; sin estado explícito se exporta el padrón aprobado.
- Exportaciones `GET /api/exportar/padron` y `GET /api/exportar/cobranzas` en CSV/JSON, con datos de instrumento enmascarados.
- El CSV usa UTF-8, separador `;` y encabezados en español; no incluye PAN/CVV ni detalle de salud.

---

## 11. API y contrato mínimo

| Método | Ruta | Descripción | Feature |
|---|---|---|---|
| `GET` | `/health` | Healthcheck: `{"status": "ok"}`. | F01 |
| `POST` | `/api/ventas` | Crea una venta completa, calcula el total y devuelve el comprobante. | F03 |
| `GET` | `/api/ventas` | Lista paginada con búsqueda y filtros por estado, plan, medio y régimen. | F18 |
| `GET` | `/api/ventas/{id}` | Devuelve el detalle de una venta con integrantes y plan. | F03 |
| `GET` | `/api/ventas/{id}/eventos` | Devuelve el linaje inmutable de la venta. | F18 |
| `PUT` | `/api/ventas/{id}` | Reemplaza un legajo pendiente/observado, recalcula y reabre la auditoría. | F15 |
| `POST` | `/api/auditar` | Ejecuta el auditor sobre las ventas pendientes y devuelve resultados y traza MCP. | F08 |
| `GET` | `/api/metricas` | Devuelve KPIs y distribuciones del negocio. | F19 |
| `GET` | `/api/exportar/padron` | Exporta padrón aprobado en CSV/JSON. | F19 |
| `GET` | `/api/exportar/cobranzas` | Exporta lote de cobranzas en CSV/JSON. | F19 |
| `GET` | `/` | Wizard web de 3 etapas. | F04 |
| `GET` | `/ventas` | Panel HTML de ventas con búsqueda y filtros. | F05/F18 |
| `GET` | `/ventas/{id}` | Ficha de legajo con línea de tiempo. | F18 |
| `GET` | `/ventas/{id}/editar` | Wizard en modo edición. | F15 |
| `GET` | `/ventas/{id}/credencial` | Credencial provisoria de una venta aprobada. | F18 |
| `GET` | `/dashboard` | Tablero ejecutivo de KPIs. | F19 |

### 11.1 Reglas de la API

- `POST /api/ventas` recibe titular, domicilio, `plan_id`, `medio_pago`, la lista de integrantes y, según el medio, `tarjeta` o `cbu`; también recibe `ddjj`, `regimen_afiliacion`, `cuil_titular` y `aporte_estimado`.
- `tarjeta` incluye marca, número, titular, vencimiento y CVV; `cbu` incluye número, entidad, titular y CUIL. El servidor valida y enmascara antes de persistir.
- `medio_pago` es obligatorio y debe ser uno de `TARJETA_CREDITO`, `CBU`, `PAGO_FACIL` o `COBRADOR_DOMICILIO`.
- El cliente **no** envía `pago_*`, `subtotal_base`, `descuento_porcentaje`, `base_bonificada`, `precio_total`, `estado` ni `observaciones`; el servidor los determina.
- F15 agrega `PUT /api/ventas/{id}`: `404` inexistente, `409` aprobada, `422` payload inválido.
- F16/F17 agregan DDJJ de salud, régimen, CUIL y aporte estimado.
- Error de validación: HTTP `422` con detalle por campo.
- Plan inexistente/inactivo: HTTP `422` o `400` con mensaje claro.
- Venta inexistente en `GET`: HTTP `404`.
- La creación y la edición son atómicas; creación `201`, edición `200`.
- Los errores no exponen trazas internas, detalles de SQL ni datos completos de instrumentos.

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
3. El total se calcula en el servidor con la tabla de precios y el medio de pago, y se persiste con su desglose.
4. La venta y sus integrantes se guardan en una sola transacción.
5. Toda venta nueva queda en `PENDIENTE_VERIFICACION`.
6. El panel lista las ventas con estado, titular, plan y total.
7. El servidor MCP expone las tres herramientas y valida sus entradas.
8. El auditor aplica las reglas y actualiza el estado con observaciones.
9. El panel permite lanzar la auditoría, muestra el resumen del LLM y la traza MCP, y expone las observaciones exactas por venta.
10. El wizard, el comprobante y el panel muestran el medio de pago y el descuento aplicado.
11. El instrumento de tarjeta/CBU se captura cuando corresponde y se persiste enmascarado, sin PAN completo ni CVV.
12. Las ventas pendientes u observadas se pueden reabrir y editar por etapas; las aprobadas son inmutables.
13. La DDJJ de salud y el régimen/aportes se persisten y se validan con R7/R8.
14. El panel permite buscar, filtrar, ver la línea de tiempo y emitir credencial provisoria.
15. El tablero ejecutivo y las exportaciones CSV/JSON usan datos enmascarados.
16. `./init.sh` y `uv run pytest` pasan antes de marcar cualquier feature como completada.
17. Cada feature cerrada queda registrada en `CHECKPOINT.md` y en un commit de Git.

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
| F09 | Contexto always-on, `STATE.md` y presupuesto de contexto. |
| F10 | Bitácora rotativa y comando `/sesion`. |
| F11 | Feature packets e intake SDD. |
| F12 | Rediseño visual del wizard y el panel. |
| F13 | Medios de pago y descuentos en la cotización. |
| F14 | Instrumentos de tarjeta/CBU, validación y persistencia enmascarada. |
| F15 | Reapertura y edición multi-etapa de ventas pendientes/observadas. |
| F16 | DDJJ de salud y regla de auditoría médica R7. |
| F17 | Régimen de afiliación, CUIL, aportes y regla R8. |
| F18 | Buscador, filtros, linaje de legajo y credencial provisoria. |
| F19 | Tablero ejecutivo y exportación CSV/JSON de padrón y cobranzas. |
