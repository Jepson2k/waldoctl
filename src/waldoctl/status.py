"""Status streaming types — Protocol for StatusBuffer + concrete result types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol, runtime_checkable

import numpy as np

from waldoctl.tools import ToolStatus


class ActionState(IntEnum):
    """State of the currently executing action on the controller."""

    IDLE = 0
    EXECUTING = 1
    ERROR = 2


@runtime_checkable
class StatusBuffer(Protocol):
    """Status snapshot yielded by ``status_stream_shared()``.

    Each field is a numpy array for zero-copy access in the hot path.
    """

    pose: np.ndarray
    """(16,) float64 — flattened 4x4 homogeneous transform."""
    angles: np.ndarray
    """(N,) float64 — joint angles in degrees."""
    speeds: np.ndarray
    """(N,) float64 — joint velocities in rad/s."""
    io: np.ndarray
    """(5,) int32 — [in1, in2, out1, out2, estop]."""
    tool_status: ToolStatus
    """Universal EOAT status (key, state, positions, etc.)."""
    joint_en: np.ndarray
    """(12,) int32 — joint enable envelope."""
    cart_en: dict[str, np.ndarray]
    """Frame name -> (12,) int32 Cartesian enable envelope."""
    action_current: str
    """Currently executing action name."""
    action_params: str
    """Brief serialization of current action parameters."""
    action_state: ActionState
    """State of the current action."""
    executing_index: int
    """Index of the command currently being executed (-1 if idle)."""
    completed_index: int
    """Index of the last completed command (-1 if none)."""
    last_checkpoint: str
    """Label of the last checkpoint reached (empty if none)."""
    tcp_speed: float
    """TCP linear velocity in mm/s."""
    simulator_active: bool
    """Whether the controller is in simulator mode."""
    collision_active: bool
    """Whether a motion was blocked/stopped by a predicted collision."""
    collision_pairs: list[tuple[str, str]]
    """Colliding pairs at the predicted colliding config.  Names are URDF link
    names, ``shape:<name>`` (program keep-out), ``install:<name>``
    (installation keep-out), or ``tool:<key>:<part>`` (attached tool geometry)
    — never backend-internal geometry identifiers."""
    scene_epoch: int
    """Monotonic counter bumped on every collision-world change; displays
    re-query ``RobotClient.shapes()`` when it moves."""
    homed: bool
    """All joints homed. Until homing, reported joint positions are
    unreferenced and backends refuse planned motion; frontends seed dry-run
    previews with this so previews mirror that gate."""
    torques: np.ndarray
    """(N,) float64 — measured joint torques [Nm]."""
    torques_ext: np.ndarray
    """(N,) float64 — external joint torque estimate [Nm]: measured torque
    minus the backend's dynamics model. A hand pushing the arm, a payload
    the model does not know."""
    enabled: bool
    """Whether the controller accepts motion."""
    warnings: list[tuple]
    """Self-clearing warning-class conditions as structured-error 6-tuples
    ``(command_index, code, title, cause, effect, remedy)`` — stale data,
    degraded loop, failed homing. Hard latches are NOT here; they surface
    through the error query/standing error."""
    link_health: dict
    """Motor-bus link health: ``state`` (backend enum/str), ``restarts``,
    ``tx_errors``, ``rx_frames``. Empty when the backend has no bus."""
    homing: dict
    """Homing progress: ``active``, ``sequence_step``, and per-actuator
    ``joints`` — (state, phase) pairs. Empty when idle and unsupported."""

    @property
    def freedrive(self) -> bool:
        """Whether the arm is back-driveable right now — hand guiding is
        actually in effect, not merely requested. A read-only property so
        backends may derive it from their own state rather than store it."""
        ...

    @property
    def mode(self) -> IntEnum:
        """Controller mode. Backend-specific enum — a read-only property
        so a backend's own enum subclass satisfies the Protocol (a plain
        attribute would be invariant); ``.name`` is the display string
        (BOOTING, IDLE, JOG, ...)."""
        ...


@dataclass
class LoopStatsResult:
    """Control-loop runtime metrics — the ``loop_stats()`` query result.

    Periods are seconds; ``can_frame_age_*`` are backend ticks (0 on
    backends without a fieldbus); ``rt_fifo``/``rt_pinned`` report whether
    the control thread actually got its real-time scheduling."""

    target_hz: float
    loop_count: int
    overrun_count: int
    mean_period_s: float
    std_period_s: float
    min_period_s: float
    max_period_s: float
    p95_period_s: float
    p99_period_s: float
    mean_hz: float
    p50_period_s: float
    p90_period_s: float
    can_frame_age_min_ticks: int
    can_frame_age_max_ticks: int
    rt_fifo: bool
    """Whether the control thread runs under a real-time scheduling policy."""
    rt_pinned: bool
    """Whether the control thread is pinned to its configured CPU."""


@dataclass
class ActivityResult:
    """What the robot is currently doing."""

    state: ActionState
    """IDLE, EXECUTING, or ERROR."""
    command: str
    """Name of the current command (empty if idle)."""
    params: str
    """Brief serialization of current command parameters."""
    error: str
    """Error description (empty if no error)."""


Inertia6 = tuple[float, float, float, float, float, float]
"""Rotational inertia about a centre of mass, end-effector-frame axes,
``(Ixx, Ixy, Iyy, Ixz, Iyz, Izz)`` [kg m^2]. All zeros is a point mass,
which is how most payloads are declared."""


@dataclass
class PayloadResult:
    """What the runtime believes the arm is carrying at the TCP.

    An inertial description, not geometry: it is what the gravity
    feedforward and torque planning use. A backend carrying nothing
    reports zeros.
    """

    mass: float
    """Payload mass [kg]; 0 = no payload."""

    com: tuple[float, float, float]
    """Centre of mass in end-effector-frame coordinates [m]."""

    inertia: Inertia6
    """See :data:`Inertia6`."""


@dataclass
class PayloadEstimate:
    """What an estimation run measured: mass and centre of mass, never the
    inertia tensor (static poses cannot excite it).

    ``determined`` is per parameter — mass, then the three first-moment
    components — and says how much the poses actually fixed, from 0 (they
    said nothing) to 1 (fixed outright). A wrist with no room to swing
    comes back near zero and the mass should not be trusted; a backend
    asked to declare such a result refuses rather than pushing noise into
    the gravity model.
    """

    mass: float
    """Estimated mass [kg]."""

    com: tuple[float, float, float]
    """Estimated centre of mass in end-effector-frame coordinates [m] —
    the same frame ``set_payload`` takes, so the estimate is declared
    unchanged."""

    determined: tuple[float, float, float, float]
    """Share of each parameter the poses fixed, 0 to 1."""

    rms_nm: float
    """Torque the estimated load leaves unexplained [Nm]."""

    rms_unloaded_nm: float
    """Torque an empty model left unexplained [Nm] — how much of the
    reading was the load at all."""

    poses: int
    """Poses measured."""


@dataclass
class PingResult:
    """Result of a connectivity check."""

    hardware_connected: bool
    """Whether the controller has a live link to robot hardware
    (serial, socket, CAN, PLC, etc.)."""


@dataclass
class ToolResult:
    """Result of a tool query."""

    tool: str
    """Currently active tool name."""
    available: list[str]
    """All available tool names."""
