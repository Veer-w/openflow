"""Self-check for the file_upload node.

Run directly: python tests/test_file_upload.py
"""

import base64
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.nodes.file_upload import file_upload_handler  # noqa: E402


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def test_parses_csv_into_rows():
    csv_bytes = b"name,age\nAlice,30\nBob,25\n"
    params = {"filename": "people.csv", "file_base64": _b64(csv_bytes)}
    result = file_upload_handler(params, {"message": "hi"})
    assert result["rows"] == [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    assert result["source_filename"] == "people.csv"
    assert result["message"] == "hi"


def test_parses_csv_numeric_columns_as_numbers_not_strings():
    csv_bytes = b"region,sales,rate\nNorth,120,4.5\nSouth,90,3.25\n"
    result = file_upload_handler({"filename": "s.csv", "file_base64": _b64(csv_bytes)}, {})
    assert result["rows"][0]["sales"] == 120
    assert isinstance(result["rows"][0]["sales"], int)
    assert result["rows"][0]["rate"] == 4.5
    assert isinstance(result["rows"][0]["rate"], float)
    assert result["rows"][0]["region"] == "North"


def test_parses_excel_into_rows():
    pd = __import__("pandas")
    frame = pd.DataFrame([{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}])
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    params = {"filename": "people.xlsx", "file_base64": _b64(buffer.getvalue())}
    result = file_upload_handler(params, {})
    assert result["rows"] == [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]


def test_rejects_unsupported_extension():
    try:
        file_upload_handler({"filename": "notes.txt", "file_base64": _b64(b"hi")}, {})
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Unsupported file type" in str(exc)


def test_rejects_missing_filename():
    try:
        file_upload_handler({"file_base64": _b64(b"hi")}, {})
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "filename" in str(exc)


def test_rejects_invalid_base64():
    try:
        file_upload_handler({"filename": "a.csv", "file_base64": "a"}, {})
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "not valid base64" in str(exc)


def main() -> None:
    tests = [obj for name, obj in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok: {test.__name__}")
    print(f"{len(tests)} passed")


if __name__ == "__main__":
    main()
