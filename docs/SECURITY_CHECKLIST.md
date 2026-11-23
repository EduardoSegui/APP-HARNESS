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

## F23 — Autenticación local, MFA, sesiones y RBAC (2026-11-23)

- [x] Datos: usuarios, hashes Argon2id, sesiones/CSRF (solo hash), secreto TOTP cifrado y recovery codes hasheados; `security_events` sin PII. F23 no agrega salud/PAN/CVV.
- [x] Rutas: públicas `/health`, `/login`, `/mfa` (sesión pendiente) y `/static`; el resto exige sesión. Roles: wizard/edición/alta OPERADOR+ADMIN; panel y legajo autenticados; dashboard/métricas/auditoría/credencial AUDITOR+ADMIN; exportaciones ADMIN.
- [x] Matriz RBAC HTML/API verificada para OPERADOR, AUDITOR y ADMIN, incluido acceso directo con ID válido a credencial/edición (403).
- [x] Validación server-side de credenciales, TOTP, recovery codes, CSRF y longitud mínima de contraseña; mensajes de login genéricos para inexistentes, inactivos y bloqueados.
- [x] CSRF en login (pre-sesión) y en POST/PUT autenticados; ausente, inválido o de otra sesión → 403 (login, API y logout).
- [x] Sin contraseñas, tokens, TOTP ni CSRF en logs o `security_events`; se guardan tipo/resultado/usuario_id/IP/request_id. PII/salud del wizard y LLM/MCP: F25.
- [x] Secretos fuera del repo: `.env` ignorado y 600, `.env.example` sin clave, DB 600; TOTP Fernet con `APP_ENCRYPTION_KEY`; sesiones y CSRF solo hash; MCP sin secretos.
- [x] Cifrado de secreto MFA y hashes de recuperación; backups cifrados/restore quedan en F26.
- [x] Rate limit 5/min por IP+usuario, lockout 15 min tras 5 fallos y sesión MFA pendiente de 10 min; rate limit del desafío MFA y límites generales quedan en F24 (riesgo residual medio).
- [x] Eventos LOGIN OK/FALLO, MFA_SETUP, MFA y LOGOUT sin PII; denegaciones, exportaciones y configuración se amplían en F27.
- [x] Retención de seguridad (12 meses) y legal hold se implementan en F27; F23 no elimina eventos.
- [x] Tests: 366 passed (auth/RBAC/CSRF/MFA/rate limit) + 111 verificaciones manuales TestClient sobre base temporal (flags, expiración, rotación, revocación, replay, recovery, IDOR, logs).
- [x] `./init.sh` y `uv run pytest` verdes.
- [x] Sin Critical/High abiertos; riesgo residual medio de rate limit MFA diferido a F24.
