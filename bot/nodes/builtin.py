from __future__ import annotations

import json
from typing import Any

from .agent import langgraph_agent_handler, multi_agent_handler
from .base import NodeRegistry, NodeSpec


def manual_trigger_handler(_params: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return payload


def set_fields_handler(params: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    fields = params.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("set_fields.fields must be a dictionary")

    merged = dict(payload)
    merged.update(fields)
    return merged


def template_handler(params: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    template = params.get("template", "")
    if not isinstance(template, str):
        raise ValueError("template.template must be a string")

    # Safe substitution: only use literal replace on known placeholders.
    text = template.replace("{{json}}", json.dumps(payload, ensure_ascii=True))
    return {"text": text, "payload": payload}


def register_builtin_nodes(registry: NodeRegistry) -> None:
    registry.register(
        NodeSpec(
            type_name="manual_trigger",
            description="Starts a workflow with provided input data.",
            handler=manual_trigger_handler,
        )
    )
    registry.register(
        NodeSpec(
            type_name="set_fields",
            description="Merges static fields into the input payload.",
            handler=set_fields_handler,
        )
    )
    registry.register(
        NodeSpec(
            type_name="template",
            description="Builds text output from a template and payload.",
            handler=template_handler,
        )
    )
    registry.register(
        NodeSpec(
            type_name="langgraph_agent",
            description="Runs one or more local Ollama-backed LangGraph agents in sequence.",
            handler=langgraph_agent_handler,
        )
    )
    registry.register(
        NodeSpec(
            type_name="multi_agent",
            description="Legacy alias for sequential multi-agent execution.",
            handler=multi_agent_handler,
        )
    )
