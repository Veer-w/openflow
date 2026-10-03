"""Self-check for the data_visualizer node's chart-selection logic.

Run directly: python tests/test_visualizer.py
Does not require Ollama - only exercises the pure data/chart helpers,
not _run_single_agent.
"""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.nodes.visualizer import (  # noqa: E402
    MAX_CHARTS,
    _find_tabular_field,
    _render_chart,
    _summarize_generic,
    _summarize_tabular,
)


def test_finds_tabular_field_auto():
    payload = {"note": "hi", "rows": [{"a": 1}, {"a": 2}]}
    field, rows = _find_tabular_field(payload, None)
    assert field == "rows"
    assert rows == [{"a": 1}, {"a": 2}]


def test_no_tabular_field_found():
    payload = {"note": "hi", "count": 3}
    field, rows = _find_tabular_field(payload, None)
    assert field is None
    assert rows is None


def test_explicit_data_field_must_be_list_of_dicts():
    payload = {"rows": "not a list"}
    field, rows = _find_tabular_field(payload, "rows")
    assert field is None
    assert rows is None


def test_summarize_tabular_picks_numeric_histogram():
    rows = [{"age": 20, "city": "NY"}, {"age": 30, "city": "NY"}, {"age": 40, "city": "LA"}]
    summary, charts = _summarize_tabular(rows)
    assert "Rows: 3" in summary
    assert charts[0]["kind"] == "histogram"
    assert charts[0]["column"] == "age"
    assert charts[0]["values"] == [20.0, 30.0, 40.0]


def test_summarize_tabular_falls_back_to_bar_for_pure_categorical():
    rows = [{"city": "NY"}, {"city": "NY"}, {"city": "LA"}]
    summary, charts = _summarize_tabular(rows)
    assert charts[0]["kind"] == "bar"
    assert charts[0]["column"] == "city"
    assert charts[0]["counts"]["NY"] == 2


def test_summarize_tabular_returns_multiple_charts_capped_at_max():
    rows = [
        {"age": 20, "score": 5.0, "city": "NY", "tier": "gold"},
        {"age": 30, "score": 7.5, "city": "LA", "tier": "silver"},
        {"age": 40, "score": 9.0, "city": "NY", "tier": "gold"},
    ]
    _summary, charts = _summarize_tabular(rows)
    assert len(charts) <= MAX_CHARTS
    kinds = [c["kind"] for c in charts]
    assert kinds.count("histogram") == 2
    columns = {c["column"] for c in charts}
    assert {"age", "score"} <= columns


def test_summarize_generic_builds_shape_chart():
    payload = {"a": [1, 2, 3], "b": "hello", "c": 5}
    summary, charts = _summarize_generic(payload)
    assert "No tabular" in summary
    assert len(charts) == 1
    assert charts[0]["kind"] == "bar"
    assert charts[0]["counts"] == {"a": 3, "b": 5, "c": 1}


def test_render_chart_produces_valid_base64_png():
    chart = {"kind": "histogram", "column": "age", "values": [1.0, 2.0, 3.0]}
    encoded = _render_chart(chart)
    decoded = base64.b64decode(encoded)
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"


def main() -> None:
    tests = [obj for name, obj in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok: {test.__name__}")
    print(f"{len(tests)} passed")


if __name__ == "__main__":
    main()
