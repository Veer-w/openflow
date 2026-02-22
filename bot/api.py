from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import app_config
from .engine import WorkflowEngine
from .models import ExecutionRecord, RunRequest, Workflow
from .nodes import register_builtin_nodes
from .nodes.base import NodeRegistry
from .store import SQLiteStore
from .tooling import tool_catalog

app = FastAPI(title="OpenFlow", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = NodeRegistry()
register_builtin_nodes(registry)
engine = WorkflowEngine(registry)
store = SQLiteStore()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/node-types")
def list_node_types() -> list[str]:
    return registry.list_types()


@app.get("/node-catalog")
def node_catalog() -> list[dict[str, str]]:
    return registry.list_specs()


@app.get("/config")
def config() -> dict[str, dict[str, object]]:
    return {
        "agent_defaults": app_config.agent_defaults(),
        "multi_agent_defaults": app_config.multi_agent_defaults(),
        "profile_8gb": app_config.profile_8gb(),
        "agent_tools": app_config.agent_tool_settings(),
    }


@app.get("/tool-catalog")
def tools() -> list[dict[str, str]]:
    return tool_catalog()


@app.post("/workflows", response_model=Workflow)
def create_workflow(workflow: Workflow) -> Workflow:
    existing = store.get_workflow(workflow.id)
    if existing:
        raise HTTPException(status_code=409, detail="Workflow id already exists")
    return store.create_workflow(workflow)


@app.post("/workflows/new", response_model=Workflow)
def create_workflow_with_generated_id(workflow: Workflow) -> Workflow:
    created = workflow.model_copy(update={"id": str(uuid.uuid4())})
    return store.create_workflow(created)


@app.get("/workflows", response_model=list[Workflow])
def list_workflows() -> list[Workflow]:
    return store.list_workflows()


@app.get("/workflows/{workflow_id}", response_model=Workflow)
def get_workflow(workflow_id: str) -> Workflow:
    workflow = store.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@app.put("/workflows/{workflow_id}", response_model=Workflow)
def update_workflow(workflow_id: str, workflow: Workflow) -> Workflow:
    if workflow.id != workflow_id:
        raise HTTPException(status_code=400, detail="Workflow id mismatch")
    updated = store.update_workflow(workflow_id, workflow)
    if updated is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return updated


@app.post("/workflows/{workflow_id}/run", response_model=ExecutionRecord)
def run_workflow(workflow_id: str, request: RunRequest) -> ExecutionRecord:
    workflow = store.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    execution = store.create_execution(workflow_id)

    try:
        result = engine.run(workflow, request.input_data)
        store.finish_execution(execution.id, status="success", result=result)
    except Exception as exc:
        store.finish_execution(execution.id, status="failed", error=str(exc))
        raise HTTPException(status_code=400, detail=f"Execution failed: {exc}") from exc

    updated = store.get_execution(execution.id)
    if updated is None:
        raise HTTPException(status_code=500, detail="Execution record missing")
    return updated


@app.get("/executions/{execution_id}", response_model=ExecutionRecord)
def get_execution(execution_id: str) -> ExecutionRecord:
    execution = store.get_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution
