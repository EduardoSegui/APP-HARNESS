# Seguridad y privacidad — Ventas Obra Social

> Documento operativo de seguridad. Complementa `CONSTITUTION.md` y `.agent/rules.md`.
> Última actualización: 2026-11-23.

## 1. Contexto y alcance

- Despliegue inicial: **LAN interna**, servidor local, sin exposición directa a Internet.
- Acceso remoto futuro: **VPN**.
- HTTPS obligatorio mediante reverse proxy; firewall y segmentación de red.
- No se usan datos reales sensibles hasta completar los controles P0 (F23, F24, F25 y backup inicial de F26).

## 2. Activos y clasificación

| Nivel | Datos | Controles |
|---|---|---|
| Público | Planes, healthcheck | Sin PII |
| Interno | Métricas agregadas, eventos sin PII | Autenticación |
| Confidencial | Nombre, DNI, CUIL, email, teléfono, domicilio, pagos | RBAC, cifrado, sin logs |
| Sensible | DDJJ y detalle de salud | Acceso restringido, cifrado, retención limitada, nunca a LLM externo |
| Secreto | API keys, claves de MFA/sesión/backup | Fuera del repo, logs, frontend y MCP |

## 3. Roles y autorización

- **OPERADOR:** alta, consulta y edición de ventas autorizadas.
- **AUDITOR:** consulta, legajos, historial, métricas y auditorías.
- **ADMIN:** usuarios, permisos, configuración, exportaciones y backups.

Reglas:
- Denegar por defecto; toda ruta nueva debe clasificarse.
- La autorización se valida en servidor; ocultar un botón no es un control.
- MFA obligatorio para ADMIN y AUDITOR; OPERADOR puede incorporarlo luego.
- No hay cuentas compartidas ni cuentas de servicio interactivas.

## 4. Autenticación y sesiones

- Contraseñas: **Argon2id**, mínimo 12 caracteres, sin texto plano ni hashes reversibles.
- Sesiones opacas, token aleatorio; solo se almacena su hash.
- Cookie `HttpOnly`, `Secure`, `SameSite=Lax`, sin datos de negocio.
- Expiración idle 30 minutos y absoluta 8 horas; rotación al autenticar.
- Logout revoca la sesión en base de datos.
- Bloqueo temporal por intentos fallidos; mensajes de error genéricos.
- Bootstrap del primer ADMIN por CLI interactivo; sin contraseña por defecto.
- SSO/LDAP queda fuera de v1; la interfaz de autenticación debe permitirlo luego.

## 5. MFA

- TOTP RFC 6238, ventana ±1, control de replay.
- Recovery codes de un solo uso, hasheados.
- Secretos TOTP cifrados con `APP_ENCRYPTION_KEY`.
- Sin SMS.
- ADMIN/AUDITOR deben enrolar en el primer acceso.

## 6. CSRF, abuso y límites

- Token CSRF por sesión; obligatorio en POST/PUT/PATCH/DELETE.
- `SameSite` es defensa adicional, no sustituto.
- Rate limiting en login, escrituras, auditoría, exportaciones y búsquedas.
- Límites de body, integrantes, búsqueda, page size y exportaciones.
- Una sola auditoría concurrente; lock/idempotencia.
- Logs de acceso sin query strings con PII.
- Headers: CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, `X-Robots-Tag` y `Cache-Control: no-store`.
- `TrustedHost` configurable; HSTS solo con HTTPS; docs/OpenAPI cerrados en
  producción.
- Errores 422 sanitizados: sin `input`, `ctx`, PAN, CVV ni salud.
- Límites: body 256 KB, 20 integrantes, búsqueda 100 caracteres, página 100 y
  exportación 5.000 filas.
- Access logs de Uvicorn filtrados; log propio sin query strings.

## 7. Datos, PII y salud

- Salud y PII nunca en logs, errores, sessionStorage ni LLM externo.
- `Cache-Control: no-store` en respuestas con PII.
- El listado API devuelve un resumen sin salud, contacto, CUIL ni instrumentos;
  el detalle completo queda para roles autorizados y el MCP local.
- `sessionStorage` solo conserva `paso` y `plan_id`; nunca PII, salud ni pagos.
- Archivos: `.env` y DB `600`; directorio `700`; usuario de servicio dedicado.
- El arranque restringe `.env` y SQLite a `600`; el despliegue debe aplicar
  propietario de servicio y directorio `700`, por ejemplo:
  `install -d -m 700 -o ventas -g ventas /opt/ventas` y
  `chown -R ventas:ventas /opt/ventas`.
- Cifrado de volumen/OS; `ddjj_detalle` y secreto MFA cifrados con
  `APP_ENCRYPTION_KEY`; migración idempotente de filas históricas.
- Backups cifrados; nunca planos ni en Git.
- Exportaciones solo ADMIN y auditadas.

## 8. LLM y MCP

- Proveedor local Ollama por defecto; comportamiento actual preservado.
- Interfaz `LLMProvider` (`services/llm.py`); proveedor externo deshabilitado
  por defecto con `LLM_EXTERNAL_ENABLED=false`.
- Habilitación externa solo ADMIN, auditada en `security_events`.
- API key en secreto/entorno, nunca en DB, frontend ni MCP.
- Payload externo: solo conteos y códigos R1–R8; nunca salud, DNI, CUIL,
  domicilio, email, teléfono ni instrumentos. El proveedor local conserva
  observaciones redactadas.
- Fallback local ante error externo; el LLM nunca decide estados.
- MCP solo `stdio`; el subproceso usa allowlist de entorno, no hereda
  `OPENAI_API_KEY`/`APP_ENCRYPTION_KEY` y no carga `.env` (`VENTAS_SKIP_DOTENV`);
  el detalle de salud se expone solo como presencia (`[cifrado]`).

## 9. Retención, legal hold y derechos

- Seguridad: `RETENCION_SEGURIDAD_DIAS=365`; job `scripts/privacidad.py retencion`.
- Comercial/salud: `RETENCION_COMERCIAL_DIAS`/`RETENCION_SALUD_DIAS` vacíos por
  defecto; no hay auto-borrado hasta definir plazos legales.
- `legal_hold` bloquea supresión/anonimización; solo se libera por decisión
  administrativa documentada.
- Flujo administrativo/CLI para acceso, rectificación, supresión y anonimización
  (`scripts/privacidad.py`), con DSR y eventos auditados.
- La supresión se implementa como anonimización de PII/salud (incluida fecha de
  nacimiento); no se borra el registro comercial ni el linaje. Un legal hold
  activo la bloquea y se exige backup verificado + confirmación del custodio.
- Aviso de privacidad versionado en `/privacidad`; consentimiento registrado en
  `consentimientos_privacidad` al confirmar una venta.
- Marco de referencia: Ley 25.326 y normativa de datos sensibles/salud; validar
  con asesoría legal.
- Documentar obligaciones de inscripción ante AAIP; ver `docs/PRIVACIDAD.md`.

## 10. Backups y recuperación

- Backup diario con API online de SQLite; cifrado obligatorio con
  `BACKUP_ENCRYPTION_KEY` (o `APP_ENCRYPTION_KEY` como fallback).
- 7 copias diarias, 4 semanales y 1 semanal desconectada.
- Clave fuera del almacenamiento de backups.
- Acceso/restore solo ADMIN/custodio; sin endpoint web de restore.
- Checksum + `PRAGMA integrity_check` y `foreign_key_check`; restore mensual.
- RPO 24 h; RTO 8 h.
- Nunca backups planos ni versionados. `backups/` está en `.gitignore`.

Comandos operativos (desde `/opt/ventas`):

```bash
uv run python scripts/backup.py crear --tipo diario
uv run python scripts/backup.py crear --tipo semanal
uv run python scripts/backup.py verificar /ruta/backup.db.enc
uv run python scripts/backup.py offline
uv run python scripts/backup.py retencion --tipo diario
# Restauración en modo mantenimiento y con confirmación explícita:
uv run python scripts/restore.py /ruta/backup.db.enc /opt/ventas/ventas.db --confirmar
```

`deploy/ventas-backup.service`/`.timer` y
`deploy/ventas-backup-semanal.service`/`.timer` son ejemplos systemd. El medio
offline debe ser un dispositivo distinto y desconectado; no dejarlo montado.
Después de restaurar, ejecutar smoke (`/health`, login, legajo) y `./init.sh`.

SQLite usa WAL, `busy_timeout`, `synchronous=FULL`, claves foráneas y
`integrity_check` al iniciar. Las ediciones usan `Venta.version` (409 si el
legajo cambió) y `venta_eventos` es append-only mediante triggers.

## 11. Logs y respuesta a incidentes

- `security_events` sin PII, con usuario, resultado, request ID, IP minimizada
  (último octeto/prefijo) y timestamp.
- Eventos: login, MFA, denegaciones, exportaciones, credencial, auditoría,
  usuarios, backups, restores, retención, legal hold y DSR.
- Retención de seguridad: 12 meses.
- Incidente: detectar, contener, preservar evidencia, erradicar, recuperar, notificar y postmortem.
- Contacto de seguridad y política de divulgación en `SECURITY.md` raíz.

## 12. Gate de seguridad

Ninguna feature con autenticación, PII, salud, exportaciones, LLM o backups puede marcar `passes` sin:
- checklist de seguridad;
- tests negativos;
- revisión del Verifier;
- `./init.sh` y `uv run pytest` verdes;
- sin hallazgos Critical/High abiertos.
