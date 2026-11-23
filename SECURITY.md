# Política de divulgación de seguridad

Este repositorio corresponde a una aplicación interna de gestión de ventas de obra social. No exponer datos reales de salud hasta completar los controles P0 definidos en `docs/SECURITY.md`.

## Reporte de vulnerabilidades

- No abrir issues públicos con detalles explotables, secretos, datos personales o capturas con PII.
- Reportar al responsable de seguridad/custodio del sistema por el canal interno definido por la organización.
- Incluir: versión/commit, impacto, pasos de reproducción mínimos y mitigación sugerida, sin datos reales.
- No ejecutar pruebas destructivas, denegación de servicio, fuerza bruta ni acceso a datos de terceros.

## Respuesta

1. Confirmar recepción y clasificar severidad.
2. Contener y preservar evidencia.
3. Corregir y agregar test de regresión.
4. Validar con `./init.sh`, `uv run pytest`, `uv lock --check`, `pip-audit`,
   `bandit`, `semgrep` y `gitleaks`.
5. Notificar según corresponda y documentar el postmortem.

## Alcance

- Aplicación FastAPI, API, templates/JS, SQLite, MCP local, LLM y scripts.
- Quedan fuera ataques a infraestructura no gestionada por el equipo (red, firewall, hipervisor), salvo configuración documentada en este repositorio.
