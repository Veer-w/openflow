from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Node(BaseModel):
    id: str
    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class Workflow(BaseModel):
    id: str
    name: str
    nodes: list[Node]
    edges: dict[str, list[str]] = Field(default_factory=dict)
    active: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunRequest(BaseModel):
    input_data: dict[str, Any] = Field(default_factory=dict)


class ExecutionRecord(BaseModel):
    id: str
    workflow_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
