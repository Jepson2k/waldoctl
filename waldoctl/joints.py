"""Joint configuration — concrete frozen dataclasses."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class PositionLimits:
    """Joint position limits in multiple unit systems.

    All arrays have shape ``(num_joints, 2)`` where columns are
    ``[lower, upper]``.
    """

    deg: NDArray[np.float64]
    """``(N, 2)`` — position limits in degrees."""
    rad: NDArray[np.float64]
    """``(N, 2)`` — position limits in radians."""


@dataclass(frozen=True)
class KinodynamicLimits:
    """Per-joint velocity, acceleration, and jerk limits.

    All arrays have shape ``(num_joints,)`` in SI units (rad/s family).
    """

    velocity: NDArray[np.float64]
    """``(N,)`` — max joint velocities in rad/s."""
    acceleration: NDArray[np.float64]
    """``(N,)`` — max joint accelerations in rad/s²."""
    jerk: NDArray[np.float64] | None = None
    """``(N,)`` — max joint jerks in rad/s³, or None."""


@dataclass(frozen=True)
class JointLimits:
    """All joint limits — position and kinodynamic."""

    position: PositionLimits
    """Position limits in degrees and radians."""
    hard: KinodynamicLimits
    """Hardware kinodynamic limits (maximum capability)."""
    jog: KinodynamicLimits
    """Jog kinodynamic limits (reduced for manual operation)."""


@dataclass(frozen=True)
class HomePosition:
    """Home / standby position in multiple unit systems.

    All arrays have shape ``(num_joints,)``.
    """

    deg: NDArray[np.float64]
    """``(N,)`` — home position in degrees."""
    rad: NDArray[np.float64]
    """``(N,)`` — home position in radians."""


@dataclass(frozen=True)
class JointsSpec:
    """Complete joint configuration for a robot.

    All array properties have their first dimension equal to ``count``.
    """

    count: int
    """Number of actuated joints."""
    names: tuple[str, ...]
    """Per-joint display names, length == ``count``."""
    limits: JointLimits
    """Position and kinodynamic limits for all joints."""
    home: HomePosition
    """Home / standby position."""
