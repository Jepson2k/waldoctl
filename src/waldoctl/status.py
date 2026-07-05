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
