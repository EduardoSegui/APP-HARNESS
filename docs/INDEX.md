# Índice de documentación

Mapa de consulta rápida. Leé solo la sección que necesitás; no cargues los documentos completos.

## Producto y flujo

| Tema | Dónde |
|---|---|
| Objetivo, alcance y actores | `docs/PRD.md` §1–3 |
| Flujo general de 3 etapas | `docs/PRD.md` §4 |
| Etapa 1: titular y grupo familiar | `docs/PRD.md` §5 |
| Etapa 2: domicilio | `docs/PRD.md` §6 |
| Etapa 3: plan, cotización y confirmación | `docs/PRD.md` §7 |
| Planes y fórmula de precio | `docs/PRD.md` §7.1–7.2 |
| Estados y transiciones | `docs/PRD.md` §8 |
| Reglas de auditoría R1–R6 | `docs/PRD.md` §9 |
| Interfaz web (wizard y panel) | `docs/PRD.md` §10 |
| API y contrato de auditoría | `docs/PRD.md` §11 |
| Capa MCP y Agente Auditor | `docs/PRD.md` §12 |

## Diseño técnico

| Tema | Dónde |
|---|---|
| Stack y dependencias | `docs/ARQUITECTURA.md` §2 |
| Estructura del repositorio | `docs/ARQUITECTURA.md` §3 |
| Configuración y arranque | `docs/ARQUITECTURA.md` §4 |
| Modelo relacional | `docs/ARQUITECTURA.md` §5 |
| Flujo de estados | `docs/ARQUITECTURA.md` §6 |
| Creación atómica de ventas | `docs/ARQUITECTURA.md` §7 |
| API y schemas | `docs/ARQUITECTURA.md` §8 |
| Interfaz web | `docs/ARQUITECTURA.md` §9 |
| MCP y auditor | `docs/ARQUITECTURA.md` §10 |
| Testing | `docs/ARQUITECTURA.md` §11 |
| Harness, roles y ciclo | `docs/ARQUITECTURA.md` §12 |
| Decisiones y riesgos | `docs/ARQUITECTURA.md` §13–14 |

## Diseño de interfaz

| Tema | Dónde |
|---|---|
| Plan de rediseño visual F12 | `docs/design/F12.md` |
| Skill `frontend-design` | `.agents/skills/frontend-design/SKILL.md` (fuente en `skills-lock.json`) |

## Harness y memoria

| Tema | Dónde |
|---|---|
| Constitución y principios SDD | `CONSTITUTION.md` |
| Estado actual y próximo paso | `STATE.md` |
| Plan y progreso | `features.json` |
| Reglas duras | `AGENTS.md` |
| Protocolo de sesión y ciclo SDD | `.agent/rules.md` |
| Rol Builder (Paso 6 SDD) | `.agent/subagents/builder.md` |
| Rol Verifier (Paso 7 SDD) | `.agent/subagents/verifier.md` |
| Ficha de la feature pendiente | `features/F0X.md` |
| Plantilla de ficha SDD | `features/_TEMPLATE.md` |
| Cómo planificar una feature | `.agent/rules.md` §Planificación |
| Historia completa | `docs/journal/` |
| Ventana reciente | `CHECKPOINT.md` |
| Presupuesto de contexto | `uv run python scripts/contexto.py --check` |
