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


@dataclass(frozen=True)
class Clearance:
    """Nearest points between the arm and one keep-out, in world metres.

    ``distance`` is signed (negative = penetration depth). ``part`` and
    ``obstacle`` use the reporting vocabulary of ``Robot.colliding_pairs``.
    """

    part: str
    obstacle: str
    distance: float
    part_point: tuple[float, float, float]
    obstacle_point: tuple[float, float, float]
