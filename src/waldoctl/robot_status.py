"""Live robot status — pose, joints, IO, tool, action history.

``RobotStatus`` is the bindable observation surface populated by the host
application's status loop. Nested sub-objects (``Pose``, ``Joints``, ``IO``,
``ToolStatus``, ``Action``) carry the per-domain leaf fields; UI bindings
target those leaves through dotted access.

**Mutate-in-place invariant**: sub-objects are constructed once and mutated
in place by writes like ``status.pose.x = ...``. Reassigning a sub-object
(``status.pose = NewPose(...)``) orphans every binding registered against
the previous instance.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from nicegui import binding

from waldoctl.notify import ChangeNotifierMixin
from waldoctl.status import ActionState
from waldoctl.tools import ToolStatus


class AngleArray:
    """Dual-representation angle array storing both degrees and radians.

    Zero-allocation access in either unit; conversion happens once at update
    time via :meth:`set_deg` or :meth:`set_rad`. Mutation is in place on the
    internal numpy buffers — bindings against an owning ``bindable_dataclass``
    field do not fire on these writes; callers should follow with
    :meth:`ChangeNotifierMixin.notify_changed` when refresh matters.
    """

    __slots__ = ("_deg", "_rad")

    def __init__(self, size: int = 6) -> None:
        self._deg = np.zeros(size, dtype=np.float64)
        self._rad = np.zeros(size, dtype=np.float64)

    @property
    def deg(self) -> np.ndarray:
        return self._deg

    @property
    def rad(self) -> np.ndarray:
        return self._rad

    def set_deg(self, values: np.ndarray) -> None:
        self._deg[:] = values
        np.deg2rad(self._deg, out=self._rad)

    def set_rad(self, values: np.ndarray) -> None:
        self._rad[:] = values
        np.rad2deg(self._rad, out=self._deg)

    def __len__(self) -> int:
        return len(self._deg)

    def __getitem__(self, idx: int) -> float:
        return float(self._deg[idx])


class ToolTimeSeries:
    """Rolling time-series buffer for tool telemetry (position, current).

    Column-oriented storage avoids zip / transpose on every read. Pushes are
    unconditional; readers consume via :meth:`get_series_if_dirty` which
    returns the full series once new samples have arrived and clears the
    dirty flag.
    """

    __slots__ = ("_ts", "_pos", "_cur", "_dirty")

    def __init__(self, max_points: int = 500) -> None:
        self._ts: deque[float] = deque(maxlen=max_points)
        self._pos: deque[float] = deque(maxlen=max_points)
        self._cur: deque[float] = deque(maxlen=max_points)
        self._dirty: bool = False

    def push(self, position: float, current: float) -> None:
        self._ts.append(time.time())
        self._pos.append(position)
        self._cur.append(current)
        self._dirty = True

    def get_series_if_dirty(
        self,
    ) -> tuple[list[float], list[float], list[float]] | None:
        if not self._dirty:
            return None
        self._dirty = False
        return list(self._ts), list(self._pos), list(self._cur)

    def clear(self) -> None:
        self._ts.clear()
        self._pos.clear()
        self._cur.clear()
        self._dirty = False


class ActionStatus(Enum):
    """Lifecycle state of one action log entry."""

    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ActionLogEntry:
    """One entry in the session-scoped action history."""

    command_name: str
    params: str = ""
    status: ActionStatus = ActionStatus.EXECUTING
    command_index: int = -1
    count: int = 1
    timestamp: float = 0.0


@binding.bindable_dataclass
class FrameJogAvailability(ChangeNotifierMixin):
    """Per-frame jog availability for X / Y / Z / Rx / Ry / Rz."""

    can_jog_pos: list[bool] = field(default_factory=lambda: [True] * 6)
    can_jog_neg: list[bool] = field(default_factory=lambda: [True] * 6)


@binding.bindable_dataclass
class CartesianJogAvailability(ChangeNotifierMixin):
    """Per-frame jog availability keyed by frame name (``TRF``, ``WRF``, …).

    Populated by the host application from the controller's per-frame
    ``cart_en`` arrays. Each value is mutated in place; never reassigned.
    """

    by_frame: dict[str, FrameJogAvailability] = field(default_factory=dict)


@binding.bindable_dataclass
class Pose(ChangeNotifierMixin):
    """Cartesian-frame live state: position, orientation, TCP speed, per-frame
    jog availability.

    **Mutate-in-place**: ``cart_jog`` is a sub-object never reassigned.
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0
    tcp_speed: float = 0.0
    cart_jog: CartesianJogAvailability = field(default_factory=CartesianJogAvailability)


@binding.bindable_dataclass(bindable_fields=["speeds", "can_jog_pos", "can_jog_neg"])
class Joints(ChangeNotifierMixin):
    """Joint-frame live state: angles, speeds, per-joint jog availability.

    ``angles`` is an :class:`AngleArray` mutated in place by ``set_deg()`` /
    ``set_rad()`` and is deliberately excluded from ``bindable_fields``: a
    ``BindableProperty`` only propagates on attribute *reassignment*, which the
    status loop never does, so an ``angles`` binding would freeze. Left
    non-bindable, ``bind_*_from`` registers it as a polled active link that
    re-reads the value each refresh tick — and the numpy buffer is never run
    through ``BindableProperty``'s ``!=`` comparison.

    ``speeds`` and ``can_jog_*`` are plain lists replaced wholesale on each
    status tick, so their bindings fire correctly on reassignment.
    """

    angles: AngleArray = field(default_factory=AngleArray)
    speeds: list[float] = field(default_factory=lambda: [0.0] * 6)
    can_jog_pos: list[bool] = field(default_factory=lambda: [True] * 6)
    can_jog_neg: list[bool] = field(default_factory=lambda: [True] * 6)


@binding.bindable_dataclass
class IO(ChangeNotifierMixin):
    """Digital IO live state.

    ``estop = 1`` means the safety chain is OK (no e-stop pressed) — matches
    the controller wire format.
    """

    inputs: list[int] = field(default_factory=list)
    outputs: list[int] = field(default_factory=list)
    estop: int = 1


@binding.bindable_dataclass
class Action(ChangeNotifierMixin):
    """Live action state: which command is currently executing (if any) plus
    the session-scoped history of past commands.

    The host application's status loop appends to ``history`` and reassigns
    ``state`` / ``current_name`` per tick. ``latest`` is a convenience
    property — bind to ``Action.history`` and use the property in a backward
    function if you need the latest entry reactively.
    """

    state: ActionState = ActionState.IDLE
    current_name: str = ""
    history: list[ActionLogEntry] = field(default_factory=list)

    @property
    def latest(self) -> ActionLogEntry | None:
        return self.history[-1] if self.history else None


@binding.bindable_dataclass
class CollisionStatus(ChangeNotifierMixin):
    """Set when a motion is blocked/stopped because it would collide — with
    itself, the attached tool, or a workspace keep-out shape.

    ``pairs`` is captured at the *predicted* colliding config — the guard halts
    before penetrating, so the robot's stopped config is collision-free.  Each
    name is a URDF link name, ``shape:<name>`` (program keep-out),
    ``install:<name>`` (installation keep-out), or ``tool:<key>:<part>``
    (attached tool geometry) — never a backend-internal geometry identifier —
    so the frontend maps pairs to scene meshes without string heuristics.
    ``pairs`` is replaced wholesale per change so its binding fires.
    """

    active: bool = False
    pairs: list[tuple[str, str]] = field(default_factory=list)


@binding.bindable_dataclass
class RobotStatus(ChangeNotifierMixin):
    """Live robot status — the public observation surface.

    Populated by the host application's status loop; consumed by every
    panel / MCP tool / extension via ``commander.status.<sub>.<leaf>``.

    **Mutate-in-place invariant**: the sub-objects (``pose``, ``joints``,
    ``io``, ``tool``, ``action``, ``collision``) are constructed once and
    mutated in place. Reassigning any of them orphans every binding registered
    against the previous instance.
    """

    connected: bool = False
    simulator_active: bool = False
    editing_mode: bool = False
    pose: Pose = field(default_factory=Pose)
    joints: Joints = field(default_factory=Joints)
    io: IO = field(default_factory=IO)
    tool: ToolStatus = field(default_factory=ToolStatus)
    action: Action = field(default_factory=Action)
    collision: CollisionStatus = field(default_factory=CollisionStatus)
    last_update: float = 0.0
