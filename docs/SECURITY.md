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
- No devolver detalle de salud/CUIL completo a integraciones que no lo necesiten.
- Archivos: `.env` y DB `600`; directorio `700`; usuario de servicio dedicado.
- Cifrado de volumen/OS; cifrado de campos sensibles (`ddjj_detalle`, secreto MFA).
- Backups cifrados; nunca planos ni en Git.
- Exportaciones solo ADMIN y auditadas.

## 8. LLM y MCP

- Proveedor local Ollama por defecto; comportamiento actual preservado.
- Interfaz `LLMProvider`; proveedor externo deshabilitado por defecto.
- Habilitación externa solo ADMIN, auditada.
- API key en secreto/entorno, nunca en DB, frontend ni MCP.
- Payload externo: solo conteos/códigos R1–R8; nunca salud, DNI, CUIL, domicilio, email, teléfono ni instrumentos.
- Fallback local ante error externo; el LLM nunca decide estados.
- MCP solo `stdio`; entorno hijo con allowlist mínima y sin secretos.

## 9. Retención, legal hold y derechos

- Seguridad: 365 días.
- Comercial/salud: sin borrado automático hasta definir plazos legales; retención configurable.
- `legal_hold` bloquea supresión/anonimización.
- Flujo administrativo para acceso, rectificación, supresión y anonimización.
- Aviso de privacidad versionado y consentimiento registrado.
- Marco de referencia: Ley 25.326 y normativa de datos sensibles/salud; validar con asesoría legal.
- Documentar obligaciones de inscripción ante AAIP.

## 10. Backups y recuperación

- Backup diario con API online de SQLite; cifrado obligatorio.
- 7 copias diarias, 4 semanales y 1 semanal desconectada.
- Clave fuera del almacenamiento de backups.
- Acceso/restore solo ADMIN/custodio; sin endpoint web de restore.
- Checksum + `PRAGMA integrity_check`; restore mensual.
- RPO 24 h; RTO 8 h.
- Nunca backups planos ni versionados.

## 11. Logs y respuesta a incidentes

- `security_events` sin PII, con usuario, resultado, request ID, IP minimizada y timestamp.
- Eventos: login, MFA, denegaciones, exportaciones, credencial, auditoría, backups, configuración y legal hold.
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
