"""Bounded, lossy value snapshots for explicitly enabled execution records.

No I/O or object repr/pickling: unsupported values become a marker. These are
debugging values, never executable inputs or a state-restoration format.
"""

from __future__ import annotations

import inspect
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from itertools import islice
from typing import Any

import numpy as np

_SECRET = re.compile(
    r"password|passwd|secret|token|credential|authorization|api.?key|private.?key", re.I
)


def snapshot_value(value: Any) -> Any:
    """Detach ordinary values with depth, item and string bounds.

    Credential-named fields are redacted. Arbitrary strings can still contain
    personal data; sharing requires the application's separate export policy.
    """
    remaining = 256

    def visit(item: Any, depth: int) -> Any:
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 6:
            return "<truncated>"
        if item is None or type(item) in (bool, int):
            return (
                item
                if not isinstance(item, int) or item.bit_length() < 256
                else "<large integer>"
            )
        if type(item) is float:
            return item if math.isfinite(item) else "<nonfinite>"
        if type(item) is str:
            return item[:256] + ("<truncated>" if len(item) > 256 else "")
        if isinstance(item, Enum):
            return visit(item.value, depth + 1)
        if isinstance(item, np.generic):
            return visit(item.item(), depth + 1)
        if isinstance(item, np.ndarray):
            if item.dtype.kind not in "biuf":
                return "<array omitted>"
            if item.size > 256:
                return {"shape": list(item.shape), "values": "<array omitted>"}
            return visit(item.tolist(), depth + 1)
        if isinstance(item, Mapping) or (
            is_dataclass(item) and not isinstance(item, type)
        ):
            pairs = (
                item.items()
                if isinstance(item, Mapping)
                else ((f.name, getattr(item, f.name)) for f in fields(item))
            )
            result = {}
            for key, child in islice(pairs, 256):
                if remaining <= 0:
                    result["<truncated>"] = True
                    break
                if type(key) is str:
                    result[key[:128]] = (
                        "<redacted>" if _SECRET.search(key) else visit(child, depth + 1)
                    )
            return result
        if type(item) in (tuple, list):
            result = []
            for child in item[:256]:
                if remaining <= 0:
                    break
                result.append(visit(child, depth + 1))
            if len(result) < len(item):
                result.append("<truncated>")
            return result
        return "<unsupported>"

    try:
        return visit(value, 0)
    except Exception:
        return "<snapshot unavailable>"


def snapshot_arguments(
    function: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    omit_first: bool = False,
) -> Any:
    """Bind positional/keyword values to their names and include defaults."""
    try:
        bound = inspect.signature(function).bind(*args, **kwargs)
        bound.apply_defaults()
        arguments = dict(bound.arguments)
        if omit_first and arguments:
            arguments.pop(next(iter(arguments)))
        return snapshot_value(arguments)
    except (TypeError, ValueError):
        return snapshot_value(
            {"args": args[1:] if omit_first else args, "kwargs": kwargs}
        )
