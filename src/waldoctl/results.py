"""Result types — Protocols for return value shapes + concrete dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray


@runtime_checkable
class IKResult(Protocol):
    """Result of an inverse kinematics solve."""

    q: NDArray[np.float64]
    """Joint angles in radians."""
    success: bool
    """Whether the solver converged within tolerance."""
    violations: str | None
    """Description of limit violations, or None."""


@dataclass
class IKResultData:
    """Concrete IKResult for use in tests and adapters."""

    q: NDArray[np.float64]
    success: bool
    violations: str | None = None
