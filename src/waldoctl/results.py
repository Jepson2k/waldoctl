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
    joint_trajectory_rad: NDArray[np.float64] | None
    """(N, num_joints) — full joint trajectory in radians, aligned with tcp_poses rows. None if unavailable."""


@dataclass(frozen=True)
class ObjectTrack:
    """Where a physical world object went during a previewed program.

    Keyed by the shape's ``name`` — a dynamic object is a ``Shape`` carrying
    ``physics``, not a separate kind of thing, so it has the same identity here
    as it does in the collision world and the readback.
    """

    name: str
    poses: NDArray[np.float64]
    """(N, 7) — [x, y, z, qw, qx, qy, qz], one row per trajectory sample,
    aligned with the segment's ``joint_trajectory_rad`` rows. A stationary
    object may carry a single row, which consumers broadcast."""
    carried: bool
    """True while the object is riding the TCP rather than free."""
    physics: bool
    """False when the preview fell back to a geometric approximation instead
    of stepping the simulator — the track is a guess, and consumers should
    render it as one."""


@runtime_checkable
class ObjectAwareDryRunResult(Protocol):
    """A ``DryRunResult`` that also reports world-object motion.

    Separate from ``DryRunResult`` on purpose: that Protocol is matched
    structurally by backends pinned to older waldoctl tags, so adding a
    required member to it would break their conformance. Consumers should use
    ``getattr(result, "object_tracks", None)``.
    """

    object_tracks: tuple[ObjectTrack, ...] | None
    """Per-object pose tracks, or None when the backend previews no physics."""


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
    joint_trajectory_rad: NDArray[np.float64] | None = None
    object_tracks: tuple[ObjectTrack, ...] | None = None
