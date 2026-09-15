"""Canonical JSON serialization."""

import json
import math
from enum import StrEnum

import pytest


class _TestEnum(StrEnum):
    FOO = "foo"
    BAR = "bar"


def test_canonical_json_sort_keys():
    from runner.serialization import canonical_json

    result = canonical_json({"z": 1, "a": 2})
    parsed = json.loads(result)
    assert list(parsed.keys()) == ["a", "z"]


def test_canonical_json_no_spaces():
    from runner.serialization import canonical_json

    result = canonical_json({"a": 1, "b": [1, 2]})
    text = result.decode("utf-8")
    assert ": " not in text.replace(": ", "")
    assert '{"a":1,"b":[1,2]}\n' == text


def test_canonical_json_trailing_newline():
    from runner.serialization import canonical_json

    result = canonical_json({"x": 1})
    assert result.endswith(b"\n")
    assert not result.endswith(b"\n\n")


def test_canonical_json_utf8():
    from runner.serialization import canonical_json

    result = canonical_json({"key": "value"})
    assert isinstance(result, bytes)
    result.decode("utf-8")


def test_canonical_json_rejects_nan():
    from runner.serialization import canonical_json

    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


def test_canonical_json_rejects_inf():
    from runner.serialization import canonical_json

    with pytest.raises(ValueError):
        canonical_json({"x": float("inf")})


def test_canonical_json_float_repr_fidelity():
    from runner.serialization import canonical_json

    val = 0.1 + 0.2
    result = canonical_json({"x": val})
    parsed = json.loads(result)
    assert parsed["x"] == val


def test_canonical_json_enum_serializes_value():
    from runner.serialization import canonical_json

    result = canonical_json({"status": _TestEnum.FOO})
    parsed = json.loads(result)
    assert parsed["status"] == "foo"


def test_canonical_json_byte_reproducible():
    from runner.serialization import canonical_json

    obj = {"b": 2, "a": [1.1, 2.2], "c": "hello"}
    assert canonical_json(obj) == canonical_json(obj)


def test_canonical_json_ensure_ascii_false():
    from runner.serialization import canonical_json

    result = canonical_json({"emoji": "\u00e9"})
    text = result.decode("utf-8")
    assert "\u00e9" in text
    assert "\\u00e9" not in text
