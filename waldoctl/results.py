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


@runtime_checkable
class DryRunResult(Protocol):
    """Result from a dry-run motion command (path preview)."""

    tcp_poses: NDArray[np.float64]
    """(N, 6) — TCP trajectory [x, y, z, rx, ry, rz] in meters + radians."""
    end_joints_rad: NDArray[np.float64]
    """(num_joints,) — final joint angles in radians."""
    duration: float
    """Trajectory duration in seconds."""
    error: object | None
    """Structured error (e.g. RobotError), or None on success."""
    valid: NDArray[np.bool_] | None
    """(N,) per-pose IK validity; None means all poses are valid."""


@dataclass
class IKResultData:
    """Concrete IKResult for use in tests and adapters."""

    q: NDArray[np.float64]
    success: bool
    violations: str | None = None


@dataclass
class DryRunResultData:
    """Concrete DryRunResult for use in tests and adapters."""

    tcp_poses: NDArray[np.float64]
    end_joints_rad: NDArray[np.float64]
    duration: float
    error: object | None = None
    valid: NDArray[np.bool_] | None = None
