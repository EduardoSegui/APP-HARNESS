# Reglas Operativas del Harness

Estas reglas son **obligatorias y no negociables** para cualquier agente (Builder, Verifier o humano) que trabaje en este repositorio.

## Reglas fundamentales

1. **Usar siempre `uv run` para ejecutar Python o tests.**
   - Correcto: `uv run python ...`, `uv run pytest`, `uv run uvicorn ...`.
   - Prohibido: `python ...`, `python3 ...`, `pytest`, `pip install ...` fuera de `uv`.
   - Las dependencias se gestionan exclusivamente con `uv add` / `uv remove` / `uv sync`.

2. **Trabajar estrictamente de a UNA feature por sesión, tomando la primera con `"passes": false` en `features.json`.**
   - Respetar el orden F01 → F02 → ... → F07.
   - No adelantar trabajo de features posteriores.
   - No mezclar refactors amplios ni cambios de alcance con la feature en curso.

3. **Prohibido marcar `"passes": true` sin que `./init.sh` y `uv run pytest` pasen al 100 %.**
   - Ambos comandos deben ejecutarse desde la raíz del repositorio y terminar con código de salida 0.
   - Además, el Verifier debe probar los endpoints y casos borde de la feature.
   - Si algo falla, la feature permanece con `"passes": false`.

4. **Actualizar `CHECKPOINT.md` y hacer un commit claro en Git al cerrar cada feature verificada.**
   - El checkpoint debe indicar sesión, feature cerrada, tests, decisiones y próximo paso.
   - El commit debe incluir la implementación, los tests y la actualización de `features.json` + `CHECKPOINT.md`.
   - Formato sugerido: `feat(F02): modelos, schemas y seed de planes`.

## Protocolo de inicio de sesión

Antes de escribir o modificar código, todo agente debe:

1. Leer `AGENTS.md`.
2. Leer este archivo (`.agent/rules.md`).
3. Leer `CHECKPOINT.md` para conocer el estado histórico.
4. Leer `features.json` e identificar la primera feature con `"passes": false`.
5. Leer `docs/PRD.md`, `docs/ARQUITECTURA.md` y el rol que corresponda en `.agent/subagents/`.

## Protocolo de cierre de feature

1. Implementar la feature y sus tests.
2. Ejecutar `./init.sh`.
3. Ejecutar `uv run pytest` (debe pasar al 100 %).
4. Probar manualmente endpoints, templates o herramientas MCP involucradas, incluidos casos borde.
5. Actualizar `"passes": true` en `features.json` únicamente para la feature verificada.
6. Registrar la sesión en `CHECKPOINT.md`.
7. Hacer `git add -A` y commit con mensaje descriptivo.
8. Confirmar con `git status` que el árbol quedó limpio.

## Prohibiciones

- No marcar features como completadas "preventivamente" ni por confianza.
- No dejar tests fallando, skipped sin justificación o deshabilitados.
- No editar `ventas.db` a mano para simular resultados.
- No introducir secretos, credenciales ni rutas absolutas personales.
- No reescribir `CHECKPOINT.md` borrando historia: solo agregar o actualizar la sección actual.
- No instalar paquetes con `pip` ni crear entornos virtuales alternativos.
- No cambiar el alcance de una feature sin actualizar antes `docs/` y `features.json`.

## Fuente de verdad

| Dato | Archivo |
|---|---|
| Reglas de trabajo | `.agent/rules.md` |
| Estado histórico y próximo paso | `CHECKPOINT.md` |
| Plan atómico y progreso | `features.json` |
| Especificación funcional | `docs/PRD.md` |
| Diseño técnico | `docs/ARQUITECTURA.md` |
| Rol de implementación | `.agent/subagents/builder.md` |
| Rol de verificación | `.agent/subagents/verifier.md` |
