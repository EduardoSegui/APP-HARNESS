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

## Auditor

El auditor se conecta al servidor MCP por `stdio` y procesa las ventas pendientes:

```bash
uv run python -m ventas_app.auditor
```

Las reglas `R1`–`R6` son determinísticas. Opcionalmente, si se configura un
proveedor compatible con OpenAI, se agrega un resumen narrativo de la corrida:

```bash
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="http://localhost:11434/v1"  # opcional, por ejemplo Ollama
export OPENAI_MODEL="qwen2.5"                       # opcional
export OPENAI_TIMEOUT="15"                          # opcional, segundos
uv run python -m ventas_app.auditor
```

Sin `OPENAI_API_KEY` no se llama al LLM. Si la API tarda o falla, el auditor
emite una advertencia y continúa con el resumen local; nunca delega la decisión
de estado al modelo.

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
- [features.json](features.json): plan atómico F01–F07.

## Estado

El proyecto se construye de a una feature por sesión. Consultar `features.json` y `CHECKPOINT.md` para el estado vigente.

> Todos los comandos de Python y tests deben ejecutarse con `uv run`.
