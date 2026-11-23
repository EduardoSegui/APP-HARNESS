# F0X — Título de la feature

> Copiá este archivo a `features/F0X.md` y completá cada sección siguiendo el ciclo SDD (7 pasos).
> La ficha debe ser autocontenida: quien la lea no debería necesitar el PRD completo.
> Peso máximo permitido: 8 KB.

---

## Objetivo

Qué problema resuelve y para qué (Paso 2 SDD: Especificación). Dos o tres oraciones claras que justifiquen el valor funcional o técnico.

## Alcance

- Qué incluye exactamente esta feature.
- Qué comportamiento observable agrega o modifica.

## Fuera de alcance

- Qué queda explícitamente excluido y postergado para otra feature.
- Qué componentes o archivos no se van a tocar bajo ninguna circunstancia.

## Clarificación y ambigüedades resueltas

> **Paso 3 SDD: Clarificación**
> Antes de planificar y codificar, consultá con el usuario cualquier supuesto o zona gris. Documentá aquí las decisiones acordadas.

- [x] **Duda / Pregunta 1:** [Descripción de la ambigüedad] → **Decisión:** [Respuesta consensuada con el usuario].
- [x] **Duda / Pregunta 2:** [Caso de borde o diseño no especificado] → **Decisión:** [Respuesta consensuada con el usuario].

## Seguridad y privacidad

> **Paso 3/4 SDD: controles de seguridad**
> Completar `docs/SECURITY_CHECKLIST.md` cuando la feature toque auth, PII, salud, exportaciones, LLM o backups.

- Datos involucrados y clasificación: ...
- Rutas/acciones y roles autorizados: ...
- Amenazas y abuso (CSRF, IDOR, XSS, DoS, filtración): ...
- Secretos, logs, retención y egress: ...
- Tests de seguridad negativos: ...

## Criterios de aceptación

- [ ] Criterio observable 1 (comportamiento visible o contrato de datos).
- [ ] Criterio observable 2 (validación o respuesta ante error).
- [ ] Conforme a los principios de `CONSTITUTION.md`.
- [ ] Tests (`uv run pytest`) y harness (`./init.sh`) en verde al 100%.

## Planificación técnica y arquitectura

> **Paso 4 SDD: Planificación**
> Diseño de la solución técnica: contratos, esquemas y componentes involucrados.

- Cambios en modelos / esquemas: ...
- Endpoints o interfaces: ...
- Interacción con MCP o subagentes (si aplica): ...

## Archivos previstos

- `src/ventas_app/...` (nuevos o a modificar)
- `tests/...` (nuevos o a modificar)
- `docs/...` (documentación o diseño si corresponde)

## Desglose de tareas (WBS)

> **Paso 5 SDD: Tareas**
> Secuencia ordenada de tareas atómicas para el Builder. Avanzar y marcar una por una.

- [ ] **Tarea 1:** Modelos de datos / migraciones / esquemas Pydantic y sus tests unitarios.
- [ ] **Tarea 2:** Capa de servicios / lógica de negocio y tests de servicio.
- [ ] **Tarea 3:** Endpoints API / controladores / integración Jinja2 y tests de integración.
- [ ] **Tarea 4:** Interfaz visual / JS / accesibilidad y tests funcionales de UI.
- [ ] **Tarea 5:** Casos de borde, validación negativa y verificación con `./init.sh`.

## Tests y casos borde

> **Paso 7 SDD: Validación**

- Caso feliz: ...
- Caso borde (máximos, mínimos, listas vacías, duplicados): ...
- Caso de error (validación defensiva, 4xx, excepciones): ...

## Referencias

- `CONSTITUTION.md` (principios aplicables)
- `docs/PRD.md` §X
- `docs/ARQUITECTURA.md` §Y
- `CHECKPOINT.md` (sesiones o features antecedentes)

## Riesgos y dependencias

- Riesgos técnicos o posibles incompatibilidades: ...
- Dependencias con features previas o bibliotecas: ...
