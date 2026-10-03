from __future__ import annotations

import base64
import csv
import io
from typing import Any


def _coerce_value(value: str) -> Any:
    if value == "":
        return value
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _parse_csv(raw: bytes) -> list[dict[str, Any]]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [{key: _coerce_value(value) for key, value in row.items()} for row in reader]


def _parse_excel(raw: bytes) -> list[dict[str, Any]]:
    import pandas as pd

    frame = pd.read_excel(io.BytesIO(raw))
    return frame.to_dict(orient="records")


def file_upload_handler(params: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Decodes an uploaded CSV/Excel file (base64) into row records for downstream nodes."""
    filename = params.get("filename")
    file_base64 = params.get("file_base64")

    if not isinstance(filename, str) or not filename:
        raise ValueError("file_upload.filename must be a non-empty string")
    if not isinstance(file_base64, str) or not file_base64:
        raise ValueError("file_upload.file_base64 must be a non-empty base64 string")

    try:
        raw = base64.b64decode(file_base64)
    except Exception as exc:
        raise ValueError(f"file_upload.file_base64 is not valid base64: {exc}") from exc

    lower_name = filename.lower()
    if lower_name.endswith(".csv"):
        rows = _parse_csv(raw)
    elif lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
        try:
            rows = _parse_excel(raw)
        except ImportError as exc:
            raise RuntimeError(
                "Missing Excel dependency. Install with: uv add pandas openpyxl"
            ) from exc
    else:
        raise ValueError(f"Unsupported file type for '{filename}'. Use .csv, .xlsx, or .xls")

    merged = dict(payload)
    merged["rows"] = rows
    merged["source_filename"] = filename
    return merged
