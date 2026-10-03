from __future__ import annotations

import base64
import io
from collections import Counter
from typing import Any

from ..config import app_config
from .agent import _run_single_agent

DEFAULT_SYSTEM_PROMPT = (
    "You are a data analyst. You are given a statistical summary of a dataset "
    "(not the raw data). Explain what the data looks like, call out any notable "
    "patterns, outliers, or distribution shape, in a few concise sentences."
)

MAX_CHARTS = 3


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _find_tabular_field(payload: dict[str, Any], data_field: str | None) -> tuple[str | None, list[dict[str, Any]] | None]:
    if data_field:
        rows = payload.get(data_field)
        if isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows):
            return data_field, rows
        return None, None

    for key, value in payload.items():
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            return key, value
    return None, None


def _summarize_tabular(rows: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    columns: dict[str, list[Any]] = {}
    for row in rows:
        for key, value in row.items():
            columns.setdefault(key, []).append(value)

    lines = [f"Rows: {len(rows)}", f"Columns: {', '.join(columns)}"]
    numeric_charts: list[dict[str, Any]] = []
    categorical_charts: list[dict[str, Any]] = []

    for name, values in columns.items():
        numeric_vals = [v for v in values if _is_number(v)]
        if len(numeric_vals) >= max(1, len(values) // 2):
            lo, hi = min(numeric_vals), max(numeric_vals)
            avg = sum(numeric_vals) / len(numeric_vals)
            lines.append(f"- {name} (numeric): min={lo}, max={hi}, mean={avg:.2f}")
            numeric_charts.append(
                {"kind": "histogram", "column": name, "values": [float(v) for v in numeric_vals]}
            )
        else:
            counts = Counter(str(v) for v in values)
            top = counts.most_common(5)
            lines.append(f"- {name} (categorical): top values={top}")
            categorical_charts.append(
                {"kind": "bar", "column": name, "counts": dict(counts.most_common(10))}
            )

    # Prefer up to 2 numeric histograms, then fill remaining slots with categorical bars.
    charts = numeric_charts[:2] + categorical_charts[: max(0, MAX_CHARTS - min(2, len(numeric_charts)))]
    charts = charts[:MAX_CHARTS]

    return "\n".join(lines), charts


def _summarize_generic(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    shapes: dict[str, int] = {}
    for key, value in payload.items():
        if isinstance(value, (list, dict, str)):
            shapes[key] = len(value)
        else:
            shapes[key] = 1

    lines = ["No tabular (list-of-records) field found. Top-level structure:"]
    for key, size in shapes.items():
        lines.append(f"- {key}: size={size}")

    chart = {"kind": "bar", "column": "top-level keys", "counts": shapes}
    return "\n".join(lines), [chart]


def _render_chart(chart: dict[str, Any]) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    try:
        if chart["kind"] == "histogram" and chart["values"]:
            ax.hist(chart["values"], bins=min(20, max(5, len(chart["values"]) // 2)))
            ax.set_xlabel(chart["column"])
            ax.set_ylabel("count")
            ax.set_title(f"Distribution of {chart['column']}")
        else:
            counts = chart.get("counts") or {}
            ax.bar(list(counts.keys()), list(counts.values()))
            ax.set_ylabel("count")
            ax.set_title(f"{chart.get('column', 'data')} breakdown")
            ax.tick_params(axis="x", rotation=45)

        buffer = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buffer, format="png")
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    finally:
        plt.close(fig)


def data_visualizer_handler(params: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Auto-detects data in the payload, charts up to 3 columns, and has a local LLM interpret it."""
    defaults = app_config.agent_defaults()
    model = params.get("model", defaults["model"])
    system_prompt = params.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
    num_ctx = params.get("num_ctx", defaults["num_ctx"])
    num_predict = params.get("num_predict", defaults["num_predict"])
    temperature = params.get("temperature", defaults["temperature"])
    data_field = params.get("data_field")

    if not isinstance(model, str) or not model:
        raise ValueError("data_visualizer.model must be a non-empty string")
    if not isinstance(system_prompt, str):
        raise ValueError("data_visualizer.system_prompt must be a string")
    if data_field is not None and not isinstance(data_field, str):
        raise ValueError("data_visualizer.data_field must be a string")

    _field_name, rows = _find_tabular_field(payload, data_field)
    if rows is not None:
        summary_text, charts = _summarize_tabular(rows)
    else:
        summary_text, charts = _summarize_generic(payload)

    chart_images = [
        {"column": chart["column"], "kind": chart["kind"], "image": _render_chart(chart)}
        for chart in charts
    ]

    try:
        interpretation = _run_single_agent(
            model=model,
            system_prompt=system_prompt,
            user_prompt=f"Dataset summary:\n{summary_text}",
            tools=[],
            num_ctx=num_ctx,
            num_predict=num_predict,
            temperature=temperature,
            max_tool_calls=1,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Missing agent dependencies. Install with: uv add langgraph langchain-ollama"
        ) from exc

    merged = dict(payload)
    merged["chart_images"] = chart_images
    merged["chart_summary"] = summary_text
    merged["agent_output"] = interpretation
    merged["agent_model"] = model
    return merged
