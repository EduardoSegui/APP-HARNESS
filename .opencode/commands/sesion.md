---
description: Orienta la sesión con estado, feature pendiente y repo
---

## Estado

!`uv run python scripts/contexto.py estado --stdout`

## Repo

!`git status --short && git log --oneline -5`

## Pedido

$ARGUMENTS

Instrucciones:

1. Si el pedido nombra una feature (F0X), usá esa; si no, la primera pendiente del estado.
2. Leé solo `features/<id>.md` si existe; si no, usá `features.json`. Leé solo las secciones de `docs/` que el packet cite.
3. No leas `docs/PRD.md` ni `docs/ARQUITECTURA.md` completos.
4. Si el pedido dice "verificar", leé `.agent/subagents/verifier.md`; si dice "implementar", leé `.agent/subagents/builder.md`.
5. Respondé en 5 líneas: feature, estado, próximo paso, riesgos y si falta planificación.
