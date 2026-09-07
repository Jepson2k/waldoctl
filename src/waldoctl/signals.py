"""Named digital channels and observations, independent of robot I/O."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class DigitalSignal:
    """A logical signal bound to one backend's digital I/O layout.

    Indices are zero-based within the input or output bank. ``active_high``
    maps the electrical level to the logical value exposed to the program.
    The layout excludes the final E-stop status bit, which cannot be mapped.
    """

    backend: str
    direction: Literal["input", "output"]
    index: int
    input_count: int
    output_count: int
    active_high: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.backend, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]{0,63}", self.backend
        ):
            raise ValueError("Signal backend must be a package identifier")
        if self.direction not in {"input", "output"}:
            raise ValueError("Signal direction must be input or output")
        if any(
            type(v) is not int or not 0 <= v <= 256
            for v in (self.input_count, self.output_count)
        ):
            raise ValueError("Digital bank sizes must be integers between 0 and 256")
        count = self.input_count if self.direction == "input" else self.output_count
        if type(self.index) is not int or not 0 <= self.index < count:
            raise ValueError("Signal index is outside its digital bank")
        if type(self.active_high) is not bool:
            raise ValueError("Signal polarity must be a boolean")

    def decode(self, levels: Sequence[int]) -> bool:
        """Decode a fresh native I/O vector, refusing a different layout."""
        if len(levels) != self.input_count + self.output_count + 1:
            raise ValueError("Controller I/O layout differs from the saved mapping")
        if any(type(v) not in (int, bool) or v not in (0, 1) for v in levels):
            raise ValueError("Digital I/O observations must contain only binary levels")
        offset = 0 if self.direction == "input" else self.input_count
        return bool(levels[offset + self.index]) == self.active_high

    def encode(self, value: bool) -> int:
        if self.direction != "output":
            raise ValueError("An input signal cannot be written")
        if type(value) is not bool:
            raise ValueError("A logical signal value must be a boolean")
        return int(value == self.active_high)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SignalObservation:
    value: bool
    observed_at: float
    source: Literal["controller", "fixture"] = "controller"

    def __post_init__(self) -> None:
        if type(self.value) is not bool:
            raise ValueError("A logical signal value must be a boolean")
        if (
            isinstance(self.observed_at, bool)
            or not isinstance(self.observed_at, (int, float))
            or not math.isfinite(self.observed_at)
            or self.observed_at < 0
        ):
            raise ValueError("Observation time must be a finite Unix timestamp")
        if self.source not in {"controller", "fixture"}:
            raise ValueError("Signal observation source must be controller or fixture")


@dataclass(frozen=True)
class SignalWaitResult:
    outcome: Literal["matched", "timeout"]
    observation: SignalObservation | None
    elapsed_s: float
