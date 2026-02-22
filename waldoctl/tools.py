"""Tool / animation hierarchy — Enums, ABCs, and frozen dataclasses."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from waldoctl.client import RobotClient


class ToolType(Enum):
    """Tool categories the web commander has GUI support for."""

    NONE = "none"
    """Bare flange or passive tool — TCP offset + 3D visual only, no panel."""
    GRIPPER = "gripper"
    """Dedicated gripper control panel."""


class GripperType(Enum):
    """Gripper sub-types — each gets different UI controls."""

    PNEUMATIC = "pneumatic"
    ELECTRIC = "electric"


# ---------------------------------------------------------------------------
# Animation descriptors — plain frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TranslationAnimation:
    """Linear motion of tool parts (gripper jaws, press-fit rams)."""

    role: str
    """Matches ``stl_files[i]["role"]`` to select which meshes move."""
    axis: tuple[float, float, float]
    """Unit vector along which the motion occurs."""
    travel_m: float
    """Max displacement per side in meters."""
    symmetric: bool = True
    """If True, paired parts (left/right) move in opposite directions."""
    state_source: str = "grip_pos"
    """Name of the ``robot_state`` field that drives this animation."""
    state_range: tuple[float, float] = (0.0, 1000.0)
    """``(min, max)`` of the state value for normalization to 0..1."""


@dataclass(frozen=True)
class RotationAnimation:
    """Rotary motion of tool parts (spindle bits, drill chucks)."""

    role: str
    """Matches ``stl_files[i]["role"]`` to select which meshes move."""
    axis: tuple[float, float, float]
    """Unit vector for the rotation axis."""
    travel_rad: float
    """Max rotation in radians."""
    symmetric: bool = True
    """If True, paired parts rotate in opposite directions."""
    state_source: str = "grip_pos"
    """Name of the ``robot_state`` field that drives this animation."""
    state_range: tuple[float, float] = (0.0, 1000.0)
    """``(min, max)`` of the state value for normalization to 0..1."""


MeshAnimation = Union[TranslationAnimation, RotationAnimation]
"""Type alias for any animation descriptor."""


# ---------------------------------------------------------------------------
# Tool specification hierarchy
# ---------------------------------------------------------------------------


class ToolSpec(ABC):
    """Base contract every tool must satisfy.

    ``key`` is unique per tool instance (e.g. ``"pneumatic_left"``).
    ``tool_type`` determines which GUI panel category the tool belongs to.
    """

    @property
    @abstractmethod
    def key(self) -> str:
        """Unique instance identifier."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        ...

    @property
    @abstractmethod
    def tool_type(self) -> ToolType:
        """GUI category — determines which panel (if any) is shown."""
        ...

    @property
    @abstractmethod
    def tcp_origin(self) -> tuple[float, float, float]:
        """(x, y, z) translation from flange to TCP in meters."""
        ...

    @property
    @abstractmethod
    def tcp_rpy(self) -> tuple[float, float, float]:
        """(roll, pitch, yaw) orientation from flange to TCP in radians."""
        ...

    @property
    def description(self) -> str:
        """Short description of the tool."""
        return ""

    @property
    def stl_files(self) -> tuple[dict, ...]:
        """STL mesh descriptors for 3D visualization.

        Each dict has ``file`` (filename), ``origin`` ([x,y,z]),
        ``rpy`` ([r,p,y]), and optional ``role`` (e.g. ``"body"``, ``"jaw"``).
        Empty tuple if no mesh is available.
        """
        return ()

    @property
    def animations(self) -> tuple[MeshAnimation, ...]:
        """Animation descriptors for movable tool parts."""
        return ()


# ---------------------------------------------------------------------------
# Gripper hierarchy — tools own their control methods
# ---------------------------------------------------------------------------


class GripperTool(ToolSpec):
    """Base for all grippers.

    All grippers support ``set_position()`` as the universal control method.
    Position is normalized: 0.0 = fully closed, 1.0 = fully open.

    How the tool communicates with hardware is an implementation detail
    of the backend (internal send callback, shared connection, etc.).
    Tool control methods become usable after the backend binds transport
    during ``Robot.create_async_client()`` or ``Robot.start()``.
    """

    @property
    @abstractmethod
    def gripper_type(self) -> GripperType:
        """Gripper sub-type."""
        ...

    @abstractmethod
    async def set_position(self, position: float, **kwargs: object) -> int:
        """Set gripper position. 0.0 = fully closed, 1.0 = fully open."""
        ...

    async def calibrate(self, **kwargs: object) -> int:
        """Calibrate the gripper. Not all grippers support this."""
        raise NotImplementedError


class PneumaticGripperTool(GripperTool):
    """Pneumatic gripper — binary open/close.

    ``set_position()`` is concrete: clamps to binary and delegates
    to the abstract ``open()``/``close()`` methods that backends implement.
    """

    @property
    @abstractmethod
    def io_port(self) -> int:
        """Digital I/O port number for open/close control."""
        ...

    async def set_position(self, position: float, **kwargs: object) -> int:
        """Binary position: > 0.5 opens, <= 0.5 closes."""
        if position > 0.5:
            return await self.open(**kwargs)
        return await self.close(**kwargs)

    @abstractmethod
    async def open(self, **kwargs: object) -> int:
        """Open the gripper."""
        ...

    @abstractmethod
    async def close(self, **kwargs: object) -> int:
        """Close the gripper."""
        ...


class ElectricGripperTool(GripperTool):
    """Electric gripper — continuous position with speed and current control."""

    @property
    @abstractmethod
    def position_range(self) -> tuple[float, float]:
        """(min, max) position range (normalized 0..1)."""
        ...

    @property
    @abstractmethod
    def speed_range(self) -> tuple[float, float]:
        """(min, max) speed range (normalized 0..1)."""
        ...

    @property
    @abstractmethod
    def current_range(self) -> tuple[int, int]:
        """(min, max) current range in mA."""
        ...

    @abstractmethod
    async def calibrate(self, **kwargs: object) -> int:
        """Calibrate the electric gripper."""
        ...


# ---------------------------------------------------------------------------
# Tool collection
# ---------------------------------------------------------------------------


class ToolsSpec(ABC):
    """Collection of available tools for a robot.

    Supports membership testing by ``ToolType`` (category) or ``str`` (key).
    """

    @property
    @abstractmethod
    def available(self) -> tuple[ToolSpec, ...]:
        """All available tool specifications, ordered for display."""
        ...

    @property
    @abstractmethod
    def default(self) -> ToolSpec:
        """Default tool (typically bare flange / "NONE")."""
        ...

    @abstractmethod
    def __getitem__(self, key: str) -> ToolSpec:
        """Look up a tool by its key. Raises ``KeyError`` if not found."""
        ...

    @abstractmethod
    def __contains__(self, item: object) -> bool:
        """Test membership by ``ToolType`` (any tool of that category?)
        or ``str`` (specific key exists?).
        """
        ...

    @abstractmethod
    def by_type(self, tool_type: ToolType) -> tuple[ToolSpec, ...]:
        """Return all tools matching the given category."""
        ...
