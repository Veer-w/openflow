from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from langchain_core.tools import StructuredTool

from .config import app_config


def _calculator(expression: str) -> str:
    allowed_names = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sqrt": math.sqrt,
    }
    allowed_chars = set("0123456789+-*/()., %abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
    if not expression or any(ch not in allowed_chars for ch in expression):
        return "Invalid expression"
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)  # noqa: S307
    except Exception as exc:
        return f"Calculation error: {exc}"
    return str(result)


def _utc_time() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_http_get_tool(allow_domains: list[str]) -> Callable[[str], str]:
    allow = {domain.strip().lower() for domain in allow_domains if domain.strip()}

    def _http_get(url: str) -> str:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return "Invalid URL"
        if allow and host not in allow:
            return f"Domain blocked. Allowed domains: {sorted(allow)}"
        try:
            req = Request(url, headers={"User-Agent": "OpenFlow-Agent/0.1"})
            with urlopen(req, timeout=8) as resp:  # noqa: S310
                body = resp.read(4000).decode("utf-8", errors="ignore")
            return body
        except Exception as exc:
            return f"HTTP error: {exc}"

    return _http_get


def _build_tavily_search_tool(max_results: int) -> Callable[[str], str]:
    def _tavily_search(query: str) -> str:
        try:
            from tavily import TavilyClient
        except ImportError as exc:
            return (
                "Missing Tavily dependency. Install with: "
                "pip install tavily-python and set TAVILY_API_KEY."
            )

        try:
            client = TavilyClient()
            response = client.search(query=query, max_results=max_results)
            results = response.get("results", [])
            compact = [
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": item.get("content"),
                }
                for item in results
            ]
            return json.dumps(compact, ensure_ascii=True)
        except Exception as exc:
            return f"Tavily error: {exc}"

    return _tavily_search


def tool_catalog() -> list[dict[str, str]]:
    return [
        {"name": "calculator", "description": "Evaluate a simple math expression."},
        {"name": "utc_time", "description": "Get current UTC timestamp."},
        {
            "name": "http_get",
            "description": "Fetch URL content from allowlisted domains only.",
        },
        {
            "name": "tavily_search",
            "description": "Search the web via Tavily API (requires TAVILY_API_KEY).",
        },
    ]


def build_agent_tools(selected: list[str]) -> list[StructuredTool]:
    settings = app_config.agent_tool_settings()
    allow_http_domains = settings["allow_http_domains"]
    tavily_max_results = int(settings["tavily_max_results"])

    registry: dict[str, StructuredTool] = {
        "calculator": StructuredTool.from_function(
            func=_calculator,
            name="calculator",
            description="Evaluate a math expression, e.g. '(42*7)/3'.",
        ),
        "utc_time": StructuredTool.from_function(
            func=_utc_time,
            name="utc_time",
            description="Return the current UTC timestamp.",
        ),
        "http_get": StructuredTool.from_function(
            func=_build_http_get_tool(allow_http_domains if isinstance(allow_http_domains, list) else []),
            name="http_get",
            description="Fetch page text from a URL. Respects allowlist.",
        ),
        "tavily_search": StructuredTool.from_function(
            func=_build_tavily_search_tool(tavily_max_results),
            name="tavily_search",
            description="Search the web with Tavily and return compact JSON results.",
        ),
    }

    resolved: list[StructuredTool] = []
    for tool_name in selected:
        tool = registry.get(tool_name)
        if tool is not None:
            resolved.append(tool)
    return resolved
