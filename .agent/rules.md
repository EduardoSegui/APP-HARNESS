# Reglas Operativas del Harness

Protocolo detallado. Las reglas duras y los comandos están en `AGENTS.md`.

## Inicio de sesión

1. OpenCode carga `AGENTS.md`; leé `STATE.md`.
2. Identificá la primera feature con `"passes": false` en `features.json`.
3. Leé el packet `features/F0X.md` si existe y solo las secciones de `docs/` que cite.
4. Leé el rol correspondiente en `.agent/subagents/`.
5. Revisá `git status` y `git log -5` para contexto reciente.

No leas `PRD.md`, `ARQUITECTURA.md` ni el historial completos.

## Builder

- Implementa exactamente una feature y sus tests.
- No modifica `passes` ni hace el commit de cierre.
- Ejecuta `uv run pytest` y `./init.sh`.
- Reporta archivos, tests, decisiones, casos borde y riesgos.

## Verifier

- Confirma que la feature es la primera pendiente.
- Revisa `git diff` y `git status`.
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

- No marcar features por confianza ni dejar tests skipped o deshabilitados.
- No editar `ventas.db` a mano para simular resultados.
- No introducir secretos, credenciales ni rutas absolutas personales.
- No borrar historia: `CHECKPOINT.md` es una ventana; lo anterior se archiva en `docs/journal/`.
- No instalar paquetes con `pip` ni crear entornos virtuales alternativos.
- No cambiar el alcance de una feature sin actualizar antes `docs/` y `features.json`.

## Presupuesto de contexto

`uv run python scripts/contexto.py --check` falla si `AGENTS.md`, `.agent/rules.md`, `STATE.md`, `CHECKPOINT.md`, los roles o un packet exceden su cap. Si falla, se recorta o se archiva; no se ignora.
