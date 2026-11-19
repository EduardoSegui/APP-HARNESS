# CONSTITUTION.md — Constitución del Repositorio

> **Capa 1: Gobernanza y Principios Inmutables**
> Ninguna especificación, plan, prompt o implementación de IA puede contradecir o ignorar las normas aquí establecidas.

---

## Principio I — Spec-First (Desarrollo Guiado por Especificaciones)
Ningún agente o desarrollador puede escribir código de producción sin una especificación previa aprobada. El alcance debe estar acotado en una ficha de feature (`features/F0X.md`) registrada en `features.json`. Se prohíbe terminantemente el *vibe coding* (programar por impulsos o prompts ambiguos sin contrato previo).

## Principio II — Separación Estricta de Roles (Builder vs. Verifier)
Existe una separación absoluta de responsabilidades para evitar sesgos de confirmación:
- **Builder:** Diseña e implementa el código y sus tests unitarios/de integración. Jamás marca una feature como aprobada (`passes: true`) ni realiza el commit de cierre.
- **Verifier:** Audita de forma independiente el código, reproduce pruebas de borde, ejecuta el harness y es el único autorizado a certificar el cumplimiento, marcar `passes: true` y commitear.

## Principio III — Clarificación Obligatoria Previa a la Construcción
Queda prohibido asumir o inventar comportamientos no especificados. Toda zona gris, duda de diseño o caso de borde no contemplado debe someterse a clarificación explícita con el usuario/stakeholder antes de comenzar la implementación. Las decisiones acordadas deben quedar documentadas en la sección `## Clarificación y ambigüedades resueltas` de la ficha.

## Principio IV — Calidad de Pruebas y Cero "Happy-Path Exclusivo"
Todo cambio de lógica de negocio o interfaz debe respaldarse con pruebas automatizadas completas:
1. Caso feliz principal.
2. Casos de borde (entradas vacías, máximos, mínimos, duplicados).
3. Casos negativos y de error (respuestas defensivas, validaciones 4xx).
No se admiten tests comentados, marcados con `skip` sin justificación ni modificaciones a aserciones existentes destinadas a ocultar fallas funcionales.

## Principio V — Desglose Atómico en Tareas (WBS)
Ninguna feature puede implementarse como un bloque monolítico indiscriminado. Cada feature debe descomponerse en una secuencia ordenada de tareas atómicas verificables (`[ ] Tarea 1`, `[ ] Tarea 2`). El Builder debe avanzar tildando el avance tarea por tarea.

## Principio VI — Invarianza y Determinismo del Entorno
- La gestión del entorno y dependencias es estrictamente controlada mediante `uv`. Se prohíbe el uso directo de `pip`, `python` del sistema o la creación de entornos virtuales desalineados.
- Las bases de datos no se manipulan manualmente con scripts ad-hoc en producción o tests; toda mutación se realiza mediante migraciones o seeds controlados.
- Se prohíbe introducir secretos, credenciales o rutas absolutas fijas al entorno local.

## Principio VII — Economía de Contexto y Memoria Compacta
Todo archivo del harness debe respetar su presupuesto de tamaño (`scripts/contexto.py --check`):
- Ningún prompt ni agente debe cargar documentación completa innecesaria (`PRD.md` o `ARQUITECTURA.md` completos). Se consulta únicamente la sección referenciada.
- La historia y bitácoras se compactan sistemáticamente (`CHECKPOINT.md` preserva solo las últimas 2 sesiones; el resto se archiva en `docs/journal/`).
