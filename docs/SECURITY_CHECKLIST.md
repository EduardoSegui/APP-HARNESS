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

## F24 — Hardening HTTP, errores seguros y anti-abuso (2026-11-23)

- [x] Datos: no agrega PII/salud; aplica headers y `no-store` a HTML/API, incluida la credencial. PAN/CBU/CVV y DDJJ quedan fuera de logs y errores.
- [x] Rutas: sin rutas públicas nuevas; `/docs`, `/redoc` y `/openapi.json` cerrados por defecto (`ENABLE_DOCS=false`). `/static` sirve solo assets; auditoría sigue AUDITOR/ADMIN y exportaciones ADMIN.
- [x] RBAC sin cambios; verificado en F24: anónimo web → 303 a login, anónimo API → 401, OPERADOR en export → 403, CSRF ausente → 403.
- [x] Validación server-side y límites: body 256 KB (413), 20 integrantes, `q` 100 (API 422; panel HTML 400), page size 100 y export 5.000 filas (422); sin escrituras laterales.
- [x] CSRF se mantiene en POST/PUT autenticados; no se modificó la matriz de F23 y los tests siguen verdes.
- [x] Sin PII/salud/PAN/CVV en errores: handler 422 elimina `input`/`ctx`; verificado con tarjeta, CBU y detalle DDJJ. Logs propios y access log de Uvicorn sin query strings.
- [x] Secretos fuera del repo: nuevas variables en `.env.example` sin valores sensibles; `.env` y `ventas.db` ignorados; MCP/LLM sin cambios.
- [x] Cifrado/permisos: sin datos nuevos; cifrado de campos y backups siguen en F25/F26.
- [x] Rate limiting/abuso: login de F23 + políticas en memoria para alta/edición, auditoría, exportaciones y búsquedas; lock global de auditoría con 409. Verificado real: 31 POST → 429 y 61 búsquedas → 429.
- [x] Eventos de seguridad: lock/rate limit no registran PII; ampliación de `security_events` para denegaciones, exportaciones y configuración queda en F27.
- [x] Retención/legal hold: sin cambios; F27.
- [x] Tests: 11 casos nuevos en `tests/test_security.py` (headers/CSP, docs, 422, 413, integrantes, búsqueda, export, lock, rate limit, logs, `onclick`) + 54 verificaciones manuales TestClient sobre base temporal.
- [x] `./init.sh` y `uv run pytest` verdes: 377 passed.
- [x] Sin Critical/High abiertos. Riesgos residuales medios: rate limit en memoria de un worker (el proxy complementa), límite de body basado en `Content-Length` (el proxy debe cortar chunked/timeouts) y CSP con CDN/`unsafe-inline` transitorios hasta F28.

## F25 — Protección de PII/salud, secretos, MCP y LLM (2026-11-23)

- [x] Datos: PII (nombre, DNI, CUIL, contacto, domicilio e instrumentos) y salud (`ddjj_detalle`); secretos LLM y clave de cifrado solo en entorno. Listado API con `VentaResumenOut`.
- [x] Rutas: sin rutas públicas nuevas; `/api/ventas` autenticado devuelve resumen; detalle autenticado conserva datos; MCP local `stdio`; LLM externo opt-in.
- [x] RBAC: sin cambios; habilitación externa por configuración de ADMIN; MCP no se expone por red.
- [x] Validación server-side y límites: sin endpoints nuevos; se mantienen los límites F24 y la migración idempotente.
- [x] CSRF: sin POST/PUT nuevos; matriz F23 intacta.
- [x] Sin PII/salud en logs, errores 422, prompts externos ni sessionStorage: externo solo conteos R1–R8; local redacta secuencias numéricas; sessionStorage solo `paso`/`plan_id`; MCP salud como `[cifrado]`.
- [x] Secretos fuera del repo/frontend/MCP: `.env` y DB ignorados y 600; subproceso MCP con allowlist, sin `OPENAI_API_KEY`/`APP_ENCRYPTION_KEY` y `VENTAS_SKIP_DOTENV=1`; API key solo en entorno.
- [x] Cifrado/permisos: `.env`/DB 600 y `ddjj_detalle` cifrado con validación criptográfica del token, no por prefijo. Se corrigió el bypass de textos `gAAAA...` y la migración los cifra; test de borde con `descifrar_texto(crudo) == detalle` y respuesta 200.
- [x] Rate limiting/abuso: sin rutas nuevas; se mantienen las políticas F24; LLM externo opt-in.
- [x] Eventos: `LLM_EXTERNO` sin PII; ampliación de denegaciones/configuración en F27.
- [x] Retención/legal hold: sin cambios; F27.
- [x] Tests: 389 passed, 12 de `test_privacy.py` (incluye `gAAAA...` y migración) + verificaciones manuales TestClient/MCP/Node.
- [x] `./init.sh` y `uv run pytest` verdes.
- [x] Sin Critical/High abiertos: bypass de cifrado corregido y revalidado.
