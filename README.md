# OpenFlow

OpenFlow is an open-source, n8n-style automation engine with a visual workflow builder and LangGraph agent nodes powered by local Ollama.

## Phase 2 capabilities

- Workflow DAG engine (`nodes` + `edges`)
- Visual builder UI (React Flow)
- Builtin node types:
  - `manual_trigger`
  - `set_fields`
  - `template`
  - `langgraph_agent` (single or multi-agent chain, local Ollama)
  - `multi_agent` (legacy alias)
  - Tool-enabled agents (`calculator`, `utc_time`, `http_get`, `tavily_search`)
- SQLite persistence for workflows and execution history
- REST API for create/list/run workflows

## Project layout

- `main.py`: ASGI entrypoint
- `config.ini`: runtime configuration for agent defaults and 8 GB profile
- `prompts.yaml`: prompt templates for single-agent and multi-agent defaults
- `bot/api.py`: FastAPI routes
- `bot/engine.py`: workflow runtime
- `bot/store.py`: SQLite storage
- `bot/models.py`: workflow/execution models
- `bot/nodes/`: node registry + builtin handlers
- `ui/`: React + Vite visual builder
- `examples/hello_workflow.json`: base sample workflow
- `examples/visual_agent_workflow.json`: LangGraph/Ollama sample workflow
- `examples/multi_agent_workflow.json`: agent-chain sample workflow

## Prerequisites

- Python 3.11+
- Node.js 20+
- Ollama installed and running locally

Pull a local model before running agent nodes:

```bash
ollama pull qwen2.5:1.5b
```

For Tavily search tool, set API key:

```bash
export TAVILY_API_KEY="your_key_here"
```

## Run backend

```bash
cd /Users/rohith/Documents/veer/bot
uv sync
uv run uvicorn main:app --reload --port 8000
```

## Run frontend

```bash
cd /Users/rohith/Documents/veer/bot/ui
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## API quickstart

### 1) Check health

```bash
curl http://127.0.0.1:8000/health
```

### 2) Check available node types and descriptions

```bash
curl http://127.0.0.1:8000/node-catalog
```

### 2.1) Check active config from `config.ini`

```bash
curl http://127.0.0.1:8000/config
```

### 2.2) Check available agent tools

```bash
curl http://127.0.0.1:8000/tool-catalog
```

### 3) Create an agent workflow

```bash
curl -X POST "http://127.0.0.1:8000/workflows" \
  -H "Content-Type: application/json" \
  --data @examples/visual_agent_workflow.json
```

### 4) Run workflow

```bash
curl -X POST "http://127.0.0.1:8000/workflows/visual-agent-flow/run" \
  -H "Content-Type: application/json" \
  -d '{"input_data": {"message": "Summarize why testability matters"}}'
```

## Notes

- Use one `langgraph_agent` node and add `agents` entries for sequential specialist workflows.
- Edit `config.ini` for runtime limits/models and `prompts.yaml` for prompt text.
- Enable tools per agent node with params like:
  - `"tools": ["calculator", "tavily_search"]`
  - `"max_tool_calls": 6`
- Agent dependencies are loaded lazily at runtime by the node handler.
