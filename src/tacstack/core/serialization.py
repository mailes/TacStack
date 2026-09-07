"""Strict debug JSON, not a lossless sensor storage format."""

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from typing import Any

import numpy as np


def to_debug_dict(value: Any) -> Any:
    """Convert supported values; reject opaque raw payloads instead of dropping them."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_debug_dict(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, np.ndarray):
        return to_debug_dict(value.tolist())
    if isinstance(value, np.generic):
        return to_debug_dict(value.item())
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Debug JSON requires string mapping keys")
        return {key: to_debug_dict(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        if not all(isinstance(item, str) for item in value):
            raise TypeError("Only sets of strings are supported")
        return sorted(value)
    if isinstance(value, (list, tuple)):
        return [to_debug_dict(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported debug payload: {type(value).__name__}")


def to_debug_json(value: Any) -> str:
    return json.dumps(to_debug_dict(value), ensure_ascii=False, sort_keys=True, allow_nan=False)
