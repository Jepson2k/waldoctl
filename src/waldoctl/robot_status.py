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
from typing import Callable

import numpy as np
from nicegui import binding

from waldoctl.status import ActionState
from waldoctl.tools import ToolStatus


# ---------------------------------------------------------------------------
# ChangeNotifierMixin
# ---------------------------------------------------------------------------


class ChangeNotifierMixin:
    """Two-channel listener pattern for cases ``bindable_dataclass`` can't
    express on its own.

    ``bindable_dataclass`` fires UI bindings on field *reassignment*. In-place
    mutations (``list.append``, ``arr[:] = ...``, nested attribute writes,
    multi-field state transitions) do not fire bindings; the mutator should
    call :meth:`notify_changed` so any registered listener can react.

    Two channels are exposed so high-frequency step events (e.g. a running
    script advancing through waypoints at ~20 Hz) can fan out to a small set
    of observers without forcing the broader change-listener chain to recompute:

    - **change channel** — ``add_change_listener`` / ``remove_change_listener`` /
      :meth:`notify_changed`. Broad state mutations; everyone subscribes.
    - **step channel** — ``add_step_listener`` / ``remove_step_listener`` /
      :meth:`notify_step_changed`. Hot script-step events; only playback /
      step-aware consumers subscribe.

    The lists are built lazily on first registration, so subclasses do not
    need to redeclare them as dataclass fields. Copy-on-write storage lets
    each ``notify_*`` iterate safely while new listeners are being added.

    ``remove_*`` uses ``!=`` (not ``is not``) so bound methods are removable
    by their function reference — each ``obj.method`` access creates a fresh
    bound-method object that fails ``is`` but compares equal by
    ``(instance, func)``.
    """

    def _get_listeners(self) -> list[Callable[[], None]]:
        try:
            return self._change_listeners  # type: ignore[attr-defined]
        except AttributeError:
            self._change_listeners: list[Callable[[], None]] = []
            return self._change_listeners

    def _get_step_listeners(self) -> list[Callable[[], None]]:
        try:
            return self._step_listeners  # type: ignore[attr-defined]
        except AttributeError:
            self._step_listeners: list[Callable[[], None]] = []
            return self._step_listeners

    def add_change_listener(self, callback: Callable[[], None]) -> None:
        listeners = self._get_listeners()
        if callback not in listeners:
            self._change_listeners = [*listeners, callback]

    def remove_change_listener(self, callback: Callable[[], None]) -> None:
        self._change_listeners = [cb for cb in self._get_listeners() if cb != callback]

    def notify_changed(self) -> None:
        for cb in self._get_listeners():
            cb()

    def add_step_listener(self, callback: Callable[[], None]) -> None:
        listeners = self._get_step_listeners()
        if callback not in listeners:
            self._step_listeners = [*listeners, callback]

    def remove_step_listener(self, callback: Callable[[], None]) -> None:
        self._step_listeners = [
            cb for cb in self._get_step_listeners() if cb != callback
        ]

    def notify_step_changed(self) -> None:
        for cb in self._get_step_listeners():
            cb()


# ---------------------------------------------------------------------------
# AngleArray
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ToolTimeSeries
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Action history
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Cartesian jog availability
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Pose — Cartesian-frame live state
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Joints — joint-frame live state
# ---------------------------------------------------------------------------


@binding.bindable_dataclass
class Joints(ChangeNotifierMixin):
    """Joint-frame live state: angles, speeds, per-joint jog availability.

    ``angles`` is an :class:`AngleArray` whose internal numpy buffers are
    mutated in place by ``set_deg()`` / ``set_rad()``; bindings to
    ``Joints.angles`` will not fire on those writes. Consumers that need
    per-joint reactive display bind through a backward function and rely on
    :meth:`ChangeNotifierMixin.notify_changed` for refresh.

    ``speeds`` and ``can_jog_*`` are plain lists, replaced wholesale on each
    status tick — bindings fire on reassignment.
    """

    angles: AngleArray = field(default_factory=AngleArray)
    speeds: list[float] = field(default_factory=lambda: [0.0] * 6)
    can_jog_pos: list[bool] = field(default_factory=lambda: [True] * 6)
    can_jog_neg: list[bool] = field(default_factory=lambda: [True] * 6)


# ---------------------------------------------------------------------------
# IO — digital IO live state
# ---------------------------------------------------------------------------


@binding.bindable_dataclass
class IO(ChangeNotifierMixin):
    """Digital IO live state.

    ``estop = 1`` means the safety chain is OK (no e-stop pressed) — matches
    the controller wire format.
    """

    inputs: list[int] = field(default_factory=list)
    outputs: list[int] = field(default_factory=list)
    estop: int = 1


# ---------------------------------------------------------------------------
# Action — current command + session history
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# RobotStatus — the locator's `status` attribute
# ---------------------------------------------------------------------------


@binding.bindable_dataclass
class RobotStatus(ChangeNotifierMixin):
    """Live robot status — the public observation surface.

    Populated by the host application's status loop; consumed by every
    panel / MCP tool / extension via ``commander.status.<sub>.<leaf>``.

    **Mutate-in-place invariant**: the sub-objects (``pose``, ``joints``,
    ``io``, ``tool``, ``action``) are constructed once and mutated in place.
    Reassigning any of them orphans every binding registered against the
    previous instance.
    """

    connected: bool = False
    simulator_active: bool = False
    editing_mode: bool = False
    pose: Pose = field(default_factory=Pose)
    joints: Joints = field(default_factory=Joints)
    io: IO = field(default_factory=IO)
    tool: ToolStatus = field(default_factory=ToolStatus)
    action: Action = field(default_factory=Action)
    last_update: float = 0.0
