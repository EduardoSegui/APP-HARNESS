# Ventas Obra Social

Aplicación web de carga de ventas de obra social en tres etapas, con cálculo automático de cotización y validación agéntica mediante MCP.

## Stack

- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- FastAPI + Uvicorn
- SQLAlchemy 2.x + SQLite
- Pydantic v2
- Jinja2 + Tailwind CSS (CDN) + JavaScript vanilla
- Servidor MCP + Agente Auditor
- pytest + httpx

## Inicio rápido

> Para datos reales usar LAN + HTTPS por reverse proxy, `COOKIE_SECURE=true` y las reglas de `docs/SECURITY.md`. El modo HTTP local es solo desarrollo.

```bash
uv sync
# Generar una clave de desarrollo para MFA:
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Agregarla como APP_ENCRYPTION_KEY en .env y usar COOKIE_SECURE=false solo en HTTP local.
uv run uvicorn ventas_app.main:app --reload --port 8000
curl http://localhost:8000/health   # {"status":"ok"}
```

Crear el primer administrador (interactivo, sin contraseña por defecto):

```bash
uv run python -m ventas_app.cli admin-bootstrap
```

El primer login de ADMIN/AUDITOR exige configurar TOTP. Los operadores se crean con `user-create`.

Abrí `http://localhost:8000/` para cargar una venta y `http://localhost:8000/ventas`
para ver el panel y ejecutar la auditoría.

## Panel y auditoría en vivo

El panel de ventas muestra el estado y la columna **Observaciones** con el motivo
exacto de aprobación o rechazo de cada venta. El botón **“Auditar Pendientes con
IA”** ejecuta `POST /api/auditar`, muestra el estado de carga, despliega un panel
colapsable con el resumen del LLM y la traza ordenada de herramientas MCP, y
actualiza las filas procesadas.

También se puede invocar directamente:

```bash
curl -X POST http://localhost:8000/api/auditar
```

La respuesta incluye `procesadas`, `aprobadas`, `observadas`, `resumen_llm`,
`llm_ok`, `advertencia` y `traza_mcp`.

## Auditor por CLI

El auditor se conecta al servidor MCP por `stdio` y procesa las ventas pendientes:

```bash
uv run python -m ventas_app.auditor
```

Las reglas `R1`–`R6` son determinísticas. Opcionalmente, si se configura un
proveedor compatible con OpenAI, se agrega un resumen narrativo de la corrida.

### Ollama local con `qwen2.5:7b`

El repositorio incluye `.env.example`. Copialo y ajustá los valores:

```bash
cp .env.example .env
```

```dotenv
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen2.5:7b
OPENAI_TIMEOUT=60
```

La aplicación carga `.env` automáticamente al iniciar (mediante
`python-dotenv`), sin sobrescribir variables ya exportadas. Con Ollama corriendo
(`ollama serve` y `ollama pull qwen2.5:7b`), iniciá la app:

```bash
uv run uvicorn ventas_app.main:app --reload --port 8000
```

El botón del panel y el CLI usan la misma configuración. Para el CLI:

```bash
uv run python -m ventas_app.auditor
```

Sin `OPENAI_API_KEY` no se llama al LLM. Si la API tarda o falla, el auditor
registra una advertencia y continúa con el resumen local; nunca delega la decisión
de estado al modelo.

## Datos de demostración

El script `scripts/cargar_demo.py` inserta cuatro ventas pendientes en
`ventas.db`: dos válidas, una con titular menor de edad (`R1`) y una con DNI
duplicado (`R2`). Es idempotente por email de demo.

```bash
uv run python scripts/cargar_demo.py
```

Después abrí `http://localhost:8000/ventas` y usá **“Auditar Pendientes con IA”**.

## Harness y contexto

El estado actual vive en `STATE.md`; no hace falta leer el historial completo.
`CHECKPOINT.md` conserva las últimas 2 sesiones y `docs/journal/` guarda el
archivo histórico. Al cerrar una sesión, el Verifier regenera `STATE.md` y rota
la bitácora con:

```bash
uv run python scripts/contexto.py estado
uv run python scripts/contexto.py rotate
```

En OpenCode, `/sesion` inyecta el estado, `git status` y los últimos commits
para orientar la sesión sin cargar todos los documentos. El presupuesto de
contexto se valida con:

```bash
uv run python scripts/contexto.py --check
```

Cada feature nueva se planifica en una ficha `features/F0X.md` creada desde
`features/_TEMPLATE.md`; sin ficha no se construye. `features.json` es el índice
y la ficha es la orden de trabajo.

## Verificación

```bash
./init.sh
uv run pytest
```

`./init.sh` valida archivos obligatorios, presupuesto de contexto y la suite
completa.

## Documentación

- [CONSTITUTION.md](CONSTITUTION.md): principios inmutables y gobernanza SDD.
- [PRD](docs/PRD.md): especificación funcional de las 3 etapas y reglas de auditoría.
- [Arquitectura](docs/ARQUITECTURA.md): diseño técnico, modelo de datos y flujo de estados.
- [Índice de documentación](docs/INDEX.md): mapa de temas a secciones.
- [Plan de diseño F12](docs/design/F12.md): dirección visual del wizard y el panel con `frontend-design`.
- [AGENTS.md](AGENTS.md): punto de entrada del harness y roles de agentes.
- [STATE.md](STATE.md): estado actual y próximo paso.
- [CHECKPOINT.md](CHECKPOINT.md): ventana de las últimas 2 sesiones.
- [Bitácora histórica](docs/journal/2026.md): sesiones anteriores.
- [features.json](features.json): plan atómico F01–F12.
- [Plantilla de ficha](features/_TEMPLATE.md): plantilla SDD para planificar features.

## Estado

El proyecto se construye de a una feature por sesión. Consultar `STATE.md` y
`features.json` para el estado vigente.

> Todos los comandos de Python y tests deben ejecutarse con `uv run`.
