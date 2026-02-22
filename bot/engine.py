from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from .models import Node, Workflow
from .nodes.base import NodeRegistry


class WorkflowEngine:
    def __init__(self, registry: NodeRegistry) -> None:
        self.registry = registry

    def run(self, workflow: Workflow, input_data: dict[str, Any]) -> dict[str, Any]:
        ordered_nodes = self._topological_sort(workflow.nodes, workflow.edges)
        results: dict[str, dict[str, Any]] = {}

        for node in ordered_nodes:
            parent_payload = self._merge_parent_payloads(node, workflow.edges, results)
            if not parent_payload:
                parent_payload = input_data

            handler = self.registry.get(node.type).handler
            results[node.id] = handler(node.params, parent_payload)

        if not ordered_nodes:
            return input_data

        return results[ordered_nodes[-1].id]

    def _merge_parent_payloads(
        self,
        node: Node,
        edges: dict[str, list[str]],
        results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        incoming: list[str] = []
        for source, targets in edges.items():
            if node.id in targets:
                incoming.append(source)

        if not incoming:
            return {}

        merged: dict[str, Any] = {}
        for source in incoming:
            merged.update(results.get(source, {}))
        return merged

    def _topological_sort(self, nodes: list[Node], edges: dict[str, list[str]]) -> list[Node]:
        node_map = {n.id: n for n in nodes}
        indegree = defaultdict(int)

        for node in nodes:
            indegree[node.id] = 0

        for source, targets in edges.items():
            if source not in node_map:
                raise ValueError(f"Unknown source node in edges: {source}")
            for target in targets:
                if target not in node_map:
                    raise ValueError(f"Unknown target node in edges: {target}")
                indegree[target] += 1

        queue = deque([node_id for node_id, deg in indegree.items() if deg == 0])
        order: list[Node] = []

        while queue:
            node_id = queue.popleft()
            order.append(node_map[node_id])
            for target in edges.get(node_id, []):
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)

        if len(order) != len(nodes):
            raise ValueError("Workflow graph has a cycle")

        return order
