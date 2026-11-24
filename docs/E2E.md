# E2E y demo con Playwright

> F31. Tooling de desarrollo; no es una dependencia de runtime.

## Requisitos

- Google Chrome instalado, o Chromium de Playwright.
- `ffmpeg` para convertir el video.
- Dependencias de desarrollo:

```bash
uv sync --all-groups
uv run playwright install chromium
```

## Tests E2E

```bash
uv run pytest -m e2e
```

El test:

1. crea una SQLite temporal;
2. siembra un `demo-admin` ficticio con contraseña y secreto TOTP efímeros;
3. inicia Uvicorn en `127.0.0.1` y un puerto libre;
4. abre Chrome;
5. inicia sesión con contraseña y TOTP;
6. crea una venta ficticia;
7. ejecuta la auditoría;
8. abre el tablero;
9. prueba reapertura de una aprobada y baja lógica;
10. detiene el servidor; la base queda en el directorio temporal de pytest
    (nunca `ventas.db`).

El `pytest` normal no ejecuta estos tests (`-m 'not e2e'`).

## Grabación

```bash
uv run python scripts/record_demo.py
```

Salida:

- `docs/demo/demo.mp4`
- `docs/demo/demo.gif`

El video no debe contener datos reales, secretos productivos, CSRF ni recovery
codes. El código TOTP que aparece es efímero y de la base de test. La contraseña
se ingresa en un campo enmascarado; el secreto TOTP solo se usa en el proceso de
test y la base no es `ventas.db`.

## TOTP y Google Authenticator

El script usa el mismo algoritmo TOTP que Google Authenticator, pero genera el
código con un secreto de test que solo se usa con la base temporal. No se necesita
una cuenta ni un teléfono real. El video principal muestra el desafío TOTP, no el
setup QR.

## Chrome DevTools

DevTools es una herramienta de inspección, no una librería para integrar en la
app. Playwright controla Chrome/Chromium y usa el protocolo de DevTools
internamente. La app no depende de DevTools en producción.

## Seguridad

- `COOKIE_SECURE=false` solo para HTTP local de la demo.
- `ALLOWED_HOSTS` restringido a localhost/127.0.0.1.
- No se usa `ventas.db` ni datos reales.
- El navegador y el servidor se cierran al finalizar; la base del test queda en
  el directorio temporal de pytest y el grabador la elimina con su `TemporaryDirectory`.
- E2E no forma parte de `./init.sh` para no exigir navegador en cada verificación.
