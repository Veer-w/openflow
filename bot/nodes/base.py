from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


NodeHandler = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


@dataclass(slots=True)
class NodeSpec:
    type_name: str
    description: str
    handler: NodeHandler


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, NodeSpec] = {}

    def register(self, spec: NodeSpec) -> None:
        self._nodes[spec.type_name] = spec

    def get(self, type_name: str) -> NodeSpec:
        if type_name not in self._nodes:
            raise KeyError(f"Unknown node type: {type_name}")
        return self._nodes[type_name]

    def list_types(self) -> list[str]:
        return sorted(self._nodes)

    def list_specs(self) -> list[dict[str, str]]:
        return [
            {"type": self._nodes[key].type_name, "description": self._nodes[key].description}
            for key in sorted(self._nodes)
        ]
