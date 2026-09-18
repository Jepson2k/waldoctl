"""Controller-owned timing for queued trajectory execution."""

import math
from dataclasses import dataclass


def validate_execution_scale(scale: float) -> float:
    """Accept 10–100% of the planned trajectory speed; pause is explicit."""
    if isinstance(scale, bool) or not math.isfinite(scale) or not 0.1 <= scale <= 1.0:
        raise ValueError(
            "Execution scale must be between 0.1 and 1; use pause() to pause"
        )
    return float(scale)


@dataclass(frozen=True)
class ExecutionSpeed:
    """Fresh controller readback, relative to the originally planned timing.

    Target zero requests a pause. Applied scale can pass through values below
    0.1 during a transition to or from rest. Neither value changes jog or
    externally streamed servo targets.
    """

    target_scale: float
    applied_scale: float
    resume_scale: float
    """Last positive target, retained while paused for explicit resume."""

    def __post_init__(self) -> None:
        validate_execution_scale(self.resume_scale)
        if isinstance(self.target_scale, bool) or self.target_scale not in (
            0,
            self.resume_scale,
        ):
            raise ValueError("Resume scale must be the retained positive target")
        if (
            isinstance(self.applied_scale, bool)
            or not math.isfinite(self.applied_scale)
            or not 0 <= self.applied_scale <= 1
        ):
            raise ValueError("Applied execution scale must be finite and in [0, 1]")

    @property
    def paused(self) -> bool:
        return self.target_scale == 0 and self.applied_scale == 0

    @property
    def transitioning(self) -> bool:
        return abs(self.target_scale - self.applied_scale) > 1e-6
