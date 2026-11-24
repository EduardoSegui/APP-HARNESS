# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

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

## Sesión 28 — F29: hardening de seguridad y datos

---
feature: F29
fecha: 2026-11-24
tests: 416 passed
harness: OK
commit: feat(F29): hardening de seguridad y datos
---

**Fecha:** 2026-11-24

**Rol:** Verifier. **Feature:** F29 — Hardening de seguridad y datos. **Estado:** verificada y aprobada.

Cifrado falla seguro ante tokens de otra clave sin re-cifrar ni exponerlos; MFA con rate limit y revocación de sesión pendiente a los 5 fallos. Eventos nuevos e históricos redactan DNI/CUIL/email/teléfono, registran username real (o `mcp-auditor`) y el DSR restaura triggers append-only tras backup verificado. `VentaUpdateIn.version` obligatoria (422/409) y legajo con CUIL enmascarado.

**Verificación:** `./init.sh` → OK; `uv run pytest` → 416 passed; pruebas manuales TestClient/SQLite sobre base temporal: 32 comprobaciones (clave ajena y no modificación, MFA 5 fallos/429 y flujo válido, eventos nuevos/históricos sin PII, actor real, 422/409, CUIL/CBU enmascarados, triggers y regresiones F23–F28). Checklist F29 completo; sin Critical/High abiertos.

**Próximo paso:** Plan completo (29/29); F30/F31 no planificadas.
