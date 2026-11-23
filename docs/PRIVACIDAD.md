# Privacidad y derechos de los titulares

> Documento operativo. No sustituye asesoría legal ni la inscripción ante la AAIP.

## 1. Marco y finalidades

- Ley 25.326 de Protección de los Datos Personales y normativa de datos sensibles/salud.
- Datos usados para gestión de afiliaciones, cotizaciones, auditoría, obligaciones legales y seguridad.
- Datos de salud: acceso restringido, cifrado en reposo y sin envío a proveedores externos.

## 2. Retención

| Categoría | Plazo | Job |
|---|---|---|
| Seguridad (`security_events`) | 365 días | `scripts/privacidad.py retencion` |
| Comercial | A definir por la organización | Sin auto-borrado |
| Salud | A definir por la organización | Sin auto-borrado |

No existe una retención universal de 10 años. Los plazos comerciales/salud deben
ser definidos y documentados por la organización; el sistema no los borra
automáticamente.

## 3. Legal hold

Un legal hold activo sobre una venta bloquea su supresión y anonimización. Debe
tener motivo y responsable. Se libera únicamente por decisión administrativa
documentada:

```bash
uv run python scripts/privacidad.py hold --venta 123 --motivo "Requerimiento legal" --actor admin
uv run python scripts/privacidad.py liberar --hold 1 --actor admin
```

## 4. Derechos (DSR)

Flujo administrativo auditado:

```bash
uv run python scripts/privacidad.py solicitud --venta 123 --tipo ACCESO --actor admin
uv run python scripts/privacidad.py solicitud --venta 123 --tipo SUPRESION --actor admin
uv run python scripts/privacidad.py resolver --id 1 --actor admin --backup /ruta/backup.db.enc --confirmar
```

- **ACCESO:** se registra y entrega la información por el canal autorizado.
- **RECTIFICACION:** se registra y se corrige por el flujo de edición.
- **SUPRESION/ANONIMIZACION:** se anonimizan PII (incluida fecha de nacimiento)
  y salud; no se borra el registro comercial ni el linaje. Un legal hold activo
  bloquea la operación.
- Toda resolución genera `security_events` y evento de linaje sin PII.
- Antes de una supresión/anonimización debe existir un backup verificado y
  confirmación explícita del custodio: `--backup RUTA --confirmar`.

## 5. Aviso y consentimiento

El aviso versionado está en `/privacidad` (`AVISO_PRIVACIDAD_VERSION`). Al
confirmar una venta con el checkbox de privacidad se registra
`consentimientos_privacidad` con la versión aceptada. Las ventas históricas
pueden carecer de constancia; no se inventa consentimiento retroactivo.

## 6. Incidentes y AAIP

Runbook mínimo:

1. Detectar y registrar el incidente sin incluir PII en el ticket.
2. Contener acceso, preservar backups/logs y evaluar alcance.
3. Erradicar, recuperar desde backup verificado y validar integridad.
4. Notificar según obligaciones legales y documentar postmortem.
5. Revisar si corresponde inscripción/actualización ante la AAIP y consultar
   asesoría legal.

## 7. Operación

- Retención de seguridad: `uv run python scripts/privacidad.py retencion`.
- Exportaciones y credenciales generan eventos de seguridad.
- Los eventos de seguridad no contienen PII; los backups están cifrados y fuera
  del repositorio.
- Revisar `docs/SECURITY.md` antes de cargar datos reales.
