"""Result types — Protocols for return value shapes + concrete dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from waldoctl.ticks import TickIndex


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
    """Whether this track is what the backend's physics says.

    True covers both a stepped simulation and an exactly-equivalent rigid
    transform — an object welded to the gripper by a grasp, or one nothing
    touched. False means the backend gave up (a step budget exhausted, no
    contact simulation at all) and approximated, so the track is a guess and
    consumers should render it as one.
    """


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


@runtime_checkable
class SimulatedDryRunResult(Protocol):
    """A backend whose dry run can also *simulate*, not only plan.

    Separate from ``DryRunResult`` for the same reason
    ``ObjectAwareDryRunResult`` is: that Protocol is matched structurally
    by backends pinned to older waldoctl tags, so a new required member
    would break their conformance. Consumers should use
    ``getattr(client, "simulate", None)`` and gate on
    ``Robot.has_physics_simulation``.

    The determinism contract is load-bearing: the same model, the same
    seed and the same commands must produce a bit-identical record.
    Hosts skip redraws on an unchanged digest, so a backend that jitters
    between identical runs makes the display flicker.
    """

    @property
    def program_length(self) -> int:
        """How many commands have been recorded so far.

        A host that wants to map a simulated row back to a source line
        reads this after each call it makes and attributes the commands
        that appeared to the line it was on. The client cannot know the
        line itself — the program is the host's, not the backend's.
        """
        ...

    def simulate(self, max_seconds: float | None = None) -> TickIndex:
        """Run everything planned so far and report what the arm did.

        ``max_seconds`` bounds SIMULATED time, so a program that never
        terminates still returns, with ``stop = "budget_exhausted"``.
        """
        ...


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
