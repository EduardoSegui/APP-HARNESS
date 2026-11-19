# Reglas Operativas del Harness — Ciclo SDD

Protocolo detallado del flujo **Spec-Driven Development (SDD)** en 7 pasos. Las reglas duras y la gobernanza inmutable están en `CONSTITUTION.md` y `AGENTS.md`.

## Inicio de sesión

1. OpenCode carga `AGENTS.md`; leé `STATE.md`.
2. Identificá la primera feature con `"passes": false` en `features.json`.
3. Leé su ficha `features/F0X.md` y solo las secciones de `docs/` que cite. Si no hay ficha, planificá; no construyas.
4. Leé el rol correspondiente en `.agent/subagents/`.
5. Revisá `git status` y `git log -5` para contexto reciente.

No leas `PRD.md`, `ARQUITECTURA.md` ni el historial completos.

## Planificación (Flujo SDD: Pasos 1 al 5)

Cuando no hay features pendientes, o el pedido es una feature nueva:

1. **Constitución (Paso 1):** Revisá `CONSTITUTION.md` para garantizar que la idea no viole principios inmutables.
2. **Especificación (Paso 2):** Copiá `features/_TEMPLATE.md` a `features/F0X.md`. Completá objetivo, alcance, fuera de alcance y criterios observables.
3. **Clarificación (Paso 3):** Identificá zonas grises o supuestos y consultá con el usuario antes de planificar. Documentá las respuestas en `## Clarificación y ambigüedades resueltas`.
4. **Planificación técnica (Paso 4):** Diseñá la arquitectura de la solución, esquemas, interfaces, archivos previstos y riesgos.
5. **Tareas (Paso 5):** Desglosá la implementación en una lista ordenada de tareas atómicas (`## Desglose de tareas (WBS)`).
6. Agregá la feature al final de `features.json` con `"passes": false` y `"packet": "features/F0X.md"`.
7. Regenerá `STATE.md` y validá con `uv run python scripts/contexto.py --check`.
8. Commiteá solo documentación: `docs(plan): F0X — ...`.
9. No escribas código hasta que la ficha exista y esté commiteada.

## Builder (Paso 6: Implementación)

- Implementa exactamente una feature y sus tests siguiendo secuencialmente el WBS de la ficha.
- No empieces si la feature no tiene ficha ni clarificación.
- No modifica `passes` ni hace el commit de cierre.
- Ejecuta `uv run pytest` y `./init.sh`.
- Reporta archivos, tests, decisiones, casos borde y riesgos.

## Verifier (Paso 7: Validación)

- Confirma que la feature es la primera pendiente.
- Revisa `git diff` y `git status`.
- Verifica cumplimiento con `CONSTITUTION.md` y los criterios de aceptación de la ficha.
- Ejecuta `./init.sh` y `uv run pytest` (100 % verde).
- Prueba el caso feliz y al menos un caso borde.
- Si falla, no marca `passes` y devuelve la feature al Builder.
- Si pasa:
  1. Marca `"passes": true` solo en esa feature.
  2. Agrega una entrada compacta en `CHECKPOINT.md` (≤30 líneas).
  3. Ejecuta `uv run python scripts/contexto.py rotate`.
  4. Regenera `STATE.md`: `uv run python scripts/contexto.py estado`.
  5. Ejecuta `./init.sh` (incluye `contexto.py --check`).
  6. Crea el commit y confirma que `git status` quedó limpio.

## Prohibiciones

- Violar cualquiera de los principios inmutables de `CONSTITUTION.md`.
- No marcar features por confianza ni dejar tests skipped o deshabilitados.
- No editar `ventas.db` a mano para simular resultados.
- No introducir secretos, credenciales ni rutas absolutas personales.
- No borrar historia: `CHECKPOINT.md` es una ventana; lo anterior se archiva en `docs/journal/`.
- No instalar paquetes con `pip` ni crear entornos virtuales alternativos.
- No cambiar el alcance de una feature sin actualizar antes `docs/` y `features.json`.

## Presupuesto de contexto

`uv run python scripts/contexto.py --check` falla si `AGENTS.md`, `.agent/rules.md`, `STATE.md`, `CHECKPOINT.md`, `CONSTITUTION.md`, los roles o un packet exceden su cap. Si falla, se recorta o se archiva; no se ignora.
