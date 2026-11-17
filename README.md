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

```bash
uv sync
uv run uvicorn ventas_app.main:app --reload --port 8000
curl http://localhost:8000/health   # {"status":"ok"}
```

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

## Verificación

```bash
./init.sh
uv run pytest
```

## Documentación

- [PRD](docs/PRD.md): especificación funcional de las 3 etapas y reglas de auditoría.
- [Arquitectura](docs/ARQUITECTURA.md): diseño técnico, modelo de datos y flujo de estados.
- [AGENTS.md](AGENTS.md): punto de entrada del harness y roles de agentes.
- [CHECKPOINT.md](CHECKPOINT.md): bitácora de sesiones.
- [features.json](features.json): plan atómico F01–F08.

## Estado

El proyecto se construye de a una feature por sesión. Consultar `features.json` y `CHECKPOINT.md` para el estado vigente.

> Todos los comandos de Python y tests deben ejecutarse con `uv run`.
