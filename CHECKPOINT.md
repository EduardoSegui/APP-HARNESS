# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

## Sesión 26 — F27: privacidad, retención, legal hold y DSR

---
feature: F27
fecha: 2026-11-23
tests: 406 passed
harness: OK
commit: feat(F27): privacidad, retención, legal hold y DSR
---

**Fecha:** 2026-11-23

**Rol:** Verifier. **Feature:** F27 — Privacidad, retención, legal hold y seguridad operativa. **Estado:** verificada y aprobada.

`security_events` sin PII con IP minimizada para login/MFA, denegaciones RBAC, exportaciones, credencial, auditoría, usuarios, backups/restore, retención, legal hold y DSR. Retención por categoría (SEGURIDAD 365 días; COMERCIAL/SALUD sin auto-borrado), job que solo elimina eventos vencidos y deja evidencia. Legal hold bloquea supresión/anonimización; DSR de acceso, rectificación, supresión y anonimización auditados. Anonimización elimina PII/salud (incluida `fecha_nacimiento_titular` y DNI) conservando venta y linaje, y exige backup verificado + `--confirmar`. Aviso versionado en `/privacidad` y consentimiento registrado en el wizard.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 406 passed; `tests/test_privacidad_f27.py` → 9 passed; `node --check` OK; pruebas manuales TestClient/SQLite/CLI sobre base temporal: rechazo sin backup/confirmación o con backup corrupto sin modificar datos, anonimización con backup real, holds bloqueando DSR, retención selectiva, eventos sin PII y F23–F26 intactos. Checklist F27 completo; sin Critical/High abiertos.

**Próximo paso:** F28 — Cadena de suministro y SDD seguro — packet: `features/F28.md`.

## Sesión 27 — F28: cadena de suministro y SDD seguro

---
feature: F28
fecha: 2026-11-23
tests: 411 passed
harness: OK
commit: feat(F28): cadena de suministro y SDD seguro
---

**Fecha:** 2026-11-23

**Rol:** Verifier. **Feature:** F28 — Cadena de suministro y SDD seguro. **Estado:** verificada y aprobada.

Lockfile reproducible, dev deps `pip-audit`/`bandit`, gate local (`uv lock --check`, pip-audit, bandit High, hashes de assets y fallback de secretos), CI/pre-commit con Semgrep/gitleaks, y Tailwind 3.4.17 + fuentes Bricolage/Public Sans self-hosted con SHA-256 y CSP sin CDN (`script-src 'self'`, `font-src 'self'`).

**Verificación:** `./init.sh` → OK (gate incluido); `uv run pytest` → 411 passed; `uv sync --locked --all-groups` y `uv lock --check` OK; pip-audit sin vulnerabilidades; bandit sin High; Semgrep 1.186.0 rc 0; gitleaks 8.30.1 sin leaks en historia y archivos versionados; 7 hashes de assets OK; CSP/HTML sin Tailwind/Google Fonts externos; F23–F27 intactos; pruebas negativas de hash alterado y secreto local detectadas.

**Próximo paso:** Plan completo (28/28).
