# Checklist de seguridad por feature

Completar en la ficha o en el reporte del Builder/Verifier.

- [ ] Datos involucrados y clasificación (público/interno/confidencial/sensible/secreto).
- [ ] Rutas y acciones nuevas clasificadas como públicas, autenticadas o por rol.
- [ ] Matriz RBAC actualizada y testeada.
- [ ] Validación server-side y límites de entrada.
- [ ] CSRF en todo POST/PUT/PATCH/DELETE autenticado.
- [ ] Sin PII/salud/PAN/CVV en logs, errores 422, prompts LLM ni sessionStorage.
- [ ] Secretos fuera del repo, frontend y subproceso MCP.
- [ ] Cifrado/permisos aplicables a datos y backups.
- [ ] Rate limiting/abuso evaluado.
- [ ] Eventos de seguridad registrados sin PII.
- [ ] Retención/legal hold evaluados.
- [ ] Tests felices, bordes y negativos de seguridad.
- [ ] `./init.sh` y `uv run pytest` verdes.
- [ ] Sin Critical/High abiertos.
