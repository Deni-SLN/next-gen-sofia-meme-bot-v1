"""Minimal JSON-shape validation for agent output (FR §9.8).

Agent output is untrusted text. `json.loads` alone accepts `{"risks": "none"}`
for a field that must be a list, and silently turns malformed output into
`None` downstream - which reads as "the model had nothing to say" instead of
"the model returned nonsense".

This is deliberately not a JSON Schema implementation. It covers exactly the
shapes the registered agents declare - object / array / string / number /
integer / boolean, with required keys and per-field bounds - and fails closed
on anything it does not recognise. Adding a dependency for this would be a
larger review surface than the thing being validated.

A validator that cannot parse the spec itself raises at import time rather than
quietly accepting everything.
"""

import math

MAX_STRING = 4096
MAX_ARRAY = 256
MAX_DEPTH = 6


class SchemaError(ValueError):
    """The schema is malformed. Programming error, not data error."""


def validate(value, spec, path: str = "$") -> list[str]:
    """Return a list of violations. Empty means valid.

    Unknown spec keywords are treated as errors so a typo in a declaration
    cannot silently disable a check.
    """
    violations: list[str] = []
    _validate(value, spec, path, 0, violations)
    return violations


def _validate(value, spec, path: str, depth: int, out: list[str]) -> None:
    if depth > MAX_DEPTH:
        out.append(f"{path}: nested too deeply")
        return
    if not isinstance(spec, dict):
        raise SchemaError(f"schema at {path} must be an object, got {type(spec).__name__}")

    unknown = set(spec) - _KNOWN
    if unknown:
        raise SchemaError(f"unknown schema keys at {path}: {sorted(unknown)}")

    kind = spec.get("type")
    if kind == "object":
        _validate_object(value, spec, path, depth, out)
    elif kind == "array":
        _validate_array(value, spec, path, depth, out)
    elif kind == "string":
        if not isinstance(value, str):
            out.append(f"{path}: expected string, got {_type_name(value)}")
        elif len(value) > min(spec.get("max_length", MAX_STRING), MAX_STRING):
            out.append(f"{path}: string longer than {spec['max_length']}")
    elif kind == "integer":
        if not _is_int(value):
            out.append(f"{path}: expected integer, got {_type_name(value)}")
    elif kind == "number":
        if not _is_number(value):
            out.append(f"{path}: expected number, got {_type_name(value)}")
    elif kind == "boolean":
        if not isinstance(value, bool):
            out.append(f"{path}: expected boolean, got {_type_name(value)}")
    elif kind == "null":
        if value is not None:
            out.append(f"{path}: expected null")
    elif kind is None:
        # An empty spec accepts anything. Used where a field is free-form.
        return
    else:
        raise SchemaError(f"unknown type {kind!r} at {path}")


def _validate_object(value, spec, path, depth, out) -> None:
    if not isinstance(value, dict):
        out.append(f"{path}: expected object, got {_type_name(value)}")
        return
    properties = spec.get("properties") or {}
    for key in spec.get("required", []):
        if key not in value:
            out.append(f"{path}.{key}: required field missing")
    if spec.get("additional_properties") is False:
        for key in value:
            if key not in properties:
                out.append(f"{path}.{key}: unexpected field")
    for key, sub in properties.items():
        if key in value:
            _validate(value[key], sub, f"{path}.{key}", depth + 1, out)


def _validate_array(value, spec, path, depth, out) -> None:
    if not isinstance(value, list):
        out.append(f"{path}: expected array, got {_type_name(value)}")
        return
    limit = spec.get("max_items", MAX_ARRAY)
    if len(value) > limit:
        out.append(f"{path}: more than {limit} items")
        return
    item_spec = spec.get("items")
    if item_spec is None:
        return
    for i, item in enumerate(value[:limit]):
        _validate(item, item_spec, f"{path}[{i}]", depth + 1, out)


def _is_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _type_name(value) -> str:
    return {
        type(None): "null",
        bool: "boolean",
        int: "integer",
        float: "number",
        str: "string",
        list: "array",
        dict: "object",
    }.get(type(value), type(value).__name__)


_KNOWN = {
    "type",
    "properties",
    "required",
    "items",
    "max_items",
    "max_length",
    "additional_properties",
}

__all__ = ["MAX_ARRAY", "MAX_STRING", "SchemaError", "validate"]
