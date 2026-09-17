"""Per-program dry-run state — simulation result + playback control.

Module name is ``dry_run_state`` to avoid clashing with the existing
``waldoctl.dry_run`` module (which hosts ``DryRunClient``).

Each open program in ``commander.programs`` carries its own bindable
``DryRun`` instance. The host application assigns the result fields (e.g.
``path_segments``) wholesale when it runs a dry-run, so bindings to those
list references fire on reassignment. ``DryRun.playback`` is a nested
sub-object whose scalars mutate continuously during playback.

**Mutate-in-place invariant**: ``dry_run.playback`` is constructed once and
mutated; never reassigned. Reassigning it would orphan every binding
registered against the previous instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from nicegui import binding

from waldoctl.notify import ChangeNotifierMixin
from waldoctl.ticks import TickIndex


@dataclass(slots=True)
class ProgramTarget:
    """One move-target produced by the dry run, addressed by editor line."""

    id: str
    line_number: int
    pose: list[float]  # [x, y, z, rx, ry, rz]
    move_type: str  # "cartesian" / "pose" / "joints"
    scene_object_id: str  # ID of the 3D marker rendered for this target
    is_valid: bool = True  # False when move failed (out of range, IK failure)

    @classmethod
    def from_dict(cls, d: dict) -> "ProgramTarget":
        return cls(**d)


@dataclass(slots=True)
class PathSegment:
    """One trajectory segment between two targets."""

    points: list[list[float]]  # [x, y, z] points along the segment
    color: str  # Hex color (green / blue / orange / red)
    is_valid: bool  # Whether the segment is IK-reachable
    line_number: int  # Source line that produced this segment
    command: int | None = None  # The TickBlock.command this segment renders
    start_row: int = 0  # Rows of the commanded record it covers
    rows: int = 0
    move_type: str = "cartesian"
    is_dashed: bool = True
    show_arrows: bool = True
    estimated_duration: float | None = None
    requested_duration: float | None = None
    timing_feasible: bool = True
    checkpoint: str | None = None
    is_travel: bool = False
    # First colliding row as an offset into this segment's rows (host-side
    # collision check against the local checker), or None when clear / not
    # checked.
    collision_step: int | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "PathSegment":
        return cls(**d)


@dataclass(slots=True)
class ToolAction:
    """One tool activation captured during simulation."""

    tcp_pose: list[float] | None
    motions: list[dict[str, Any]]
    target_positions: tuple[float, ...]
    activation_type: str
    line_number: int
    method: str
    start_positions: tuple[float, ...] = ()
    estimated_duration: float = 0.0
    sleep_offset: float = 0.0
    segment_index: int = -1
    tcp_path: list[list[float]] | None = None
    # The program index of the action's own command; ``segment_index`` is
    # derived from it by the host.
    command: int = -1


@dataclass(slots=True)
class ToolSelection:
    """One ``select_tool()`` call captured during simulation."""

    tool_key: str
    variant_key: str = ""
    segment_index: int = -1
    line_number: int = 0
    command: int = -1


@dataclass
class ShapeChange:
    """One ``set_shapes()`` call captured during simulation.

    Replayed at segment boundaries during collision marking so each segment
    is checked against the world that was active at its point in the program
    (mirrors :class:`ToolSelection`).
    """

    shapes: tuple = ()
    segment_index: int = -1
    line_number: int = 0
    command: int = -1


@binding.bindable_dataclass
class Playback(ChangeNotifierMixin):
    """Playback control state for one program's dry-run.

    Mutated continuously during play / pause / step / scrub. Hosted as a
    sub-object on :class:`DryRun`; never reassigned.

    ``executing_command`` and ``executing_step_at_end`` track command
    lifecycle for running scripts: when a user script is executing, it
    advances through the program's commands and the host application updates
    these to distinguish "command N just started" from "command N just
    completed".

    The :meth:`ChangeNotifierMixin.add_step_listener` channel on this object
    carries that high-frequency stream: the host fires it whenever those
    fields advance (script start, command start, command complete), so
    plugins can react per-command on this program alone.
    """

    is_playing: bool = False
    """True while the timeline is advancing automatically."""
    is_active: bool = False
    """True while the playback timer is alive (playing OR paused mid-scrub).
    Distinguishes 'playback session in progress' from 'idle'."""
    current_step: int = 0
    """0-indexed step in the timeline."""
    playback_time: float = 0.0
    """Seconds elapsed in the current playback timeline."""
    playback_speed: float = 1.0
    """Playback rate multiplier (1.0 = realtime)."""
    active_cursor_line: int = 0
    """1-indexed editor line under the cursor (0 = none)."""
    executing_command: int = -1
    """Program index of the command the running script is executing (-1 =
    idle): the same index the dry run's ``TickBlock.command`` and
    ``PathSegment.command`` carry, so the host resolves it to a segment by
    lookup, never by position. Updated by the script-execution lifecycle,
    not by playback."""
    executing_step_at_end: bool = False
    """False = the command just started; True = it just completed. Together
    with ``executing_command`` this distinguishes "started N" from
    "completed N" for step-channel listeners."""


@binding.bindable_dataclass(
    bindable_fields=[
        "targets",
        "path_segments",
        "tool_actions",
        "tool_selections",
        "total_steps",
        "total_duration",
        "final_joints_rad",
        "revision",
        "playback",
    ]
)
class DryRun(ChangeNotifierMixin):
    """Per-program dry-run state — simulation result + playback control.

    The host application assigns the result fields (``targets``,
    ``path_segments``, ``tool_actions``, etc.) wholesale when it runs a
    dry-run, so bindings against those list references fire on each new run.

    Playback is driven externally: the host's playback controller mutates the
    ``playback`` sub-object's leaf fields in place. This class carries no
    playback methods of its own.

    ``last_sim_joints_deg``, ``commanded`` and ``predicted`` are
    intentionally excluded from the bindable field set: they hold numpy
    arrays, and NiceGUI's ``BindableProperty`` setter does ``old != new``
    which on arrays returns an element-wise array (not a scalar bool),
    raising ``ValueError`` on assignment. They are still normal dataclass
    attributes; they just aren't reactive — the host assigns
    ``path_segments`` (derived from ``commanded``) right after them, and
    that assignment is what bindings see.
    """

    # Result fields — assigned wholesale by the host when it runs a dry-run.
    targets: list[ProgramTarget] = field(default_factory=list)
    path_segments: list[PathSegment] = field(default_factory=list)
    tool_actions: list[ToolAction] = field(default_factory=list)
    tool_selections: list[ToolSelection] = field(default_factory=list)
    total_steps: int = 0
    total_duration: float = 0.0

    # Position-drift tracking — "did the robot move since the last sim?"
    final_joints_rad: list[float] | None = None
    last_sim_joints_deg: np.ndarray | None = None

    # The two records of the program, and which edit each one answers.
    # ``revision`` is bumped by the host on every change that re-plans; a
    # pass carries the revision it was launched for and lands only against
    # it, so a slow predicted pass never draws over a newer plan.
    revision: int = 0
    commanded: TickIndex | None = None
    commanded_revision: int = -1
    predicted: TickIndex | None = None
    predicted_revision: int = -1

    # Playback sub-object — mutated in place during playback.
    playback: Playback = field(default_factory=Playback)

    @property
    def predicted_current(self) -> TickIndex | None:
        """The predicted record iff it answers the commanded one on screen;
        None otherwise, which readers treat as predicted == commanded."""
        if self.predicted is None or self.predicted_revision != self.commanded_revision:
            return None
        return self.predicted
