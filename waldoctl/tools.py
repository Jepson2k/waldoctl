"""Tool / animation hierarchy — Enums, ABCs, and concrete implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


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
# Animation hierarchy
# ---------------------------------------------------------------------------


class MeshAnimation(ABC):
    """Base for all tool part animations.

    Each animation describes how a single role group of STL meshes moves
    in response to a robot state field.
    """

    @property
    @abstractmethod
    def role(self) -> str:
        """Matches ``stl_files[i]["role"]`` to select which meshes move."""
        ...

    @property
    @abstractmethod
    def axis(self) -> tuple[float, float, float]:
        """Unit vector along which the motion occurs."""
        ...

    @property
    def symmetric(self) -> bool:
        """If True, paired parts (left/right) move in opposite directions."""
        return True

    @property
    def state_source(self) -> str:
        """Name of the ``robot_state`` field that drives this animation."""
        return "grip_pos"

    @property
    def state_range(self) -> tuple[float, float]:
        """``(min, max)`` of the state value for normalization to 0..1."""
        return (0.0, 1000.0)


class TranslationAnimation(MeshAnimation):
    """Linear motion of tool parts (gripper jaws, press-fit rams)."""

    @property
    @abstractmethod
    def travel_m(self) -> float:
        """Max displacement per side in meters."""
        ...


class RotationAnimation(MeshAnimation):
    """Rotary motion of tool parts (spindle bits, drill chucks)."""

    @property
    @abstractmethod
    def travel_rad(self) -> float:
        """Max rotation in radians."""
        ...


class TranslationAnimationData(TranslationAnimation):
    """Concrete frozen translation animation descriptor."""

    __slots__ = (
        "_role", "_axis", "_travel_m",
        "_symmetric", "_state_source", "_state_range",
    )

    def __init__(
        self,
        *,
        role: str,
        axis: tuple[float, float, float],
        travel_m: float,
        symmetric: bool = True,
        state_source: str = "grip_pos",
        state_range: tuple[float, float] = (0.0, 1000.0),
    ) -> None:
        object.__setattr__(self, "_role", role)
        object.__setattr__(self, "_axis", axis)
        object.__setattr__(self, "_travel_m", travel_m)
        object.__setattr__(self, "_symmetric", symmetric)
        object.__setattr__(self, "_state_source", state_source)
        object.__setattr__(self, "_state_range", state_range)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("TranslationAnimationData is immutable")

    @property
    def role(self) -> str:
        return self._role

    @property
    def axis(self) -> tuple[float, float, float]:
        return self._axis

    @property
    def travel_m(self) -> float:
        return self._travel_m

    @property
    def symmetric(self) -> bool:
        return self._symmetric

    @property
    def state_source(self) -> str:
        return self._state_source

    @property
    def state_range(self) -> tuple[float, float]:
        return self._state_range

    def __repr__(self) -> str:
        return (
            f"TranslationAnimationData(role={self._role!r}, axis={self._axis}, "
            f"travel_m={self._travel_m})"
        )


class RotationAnimationData(RotationAnimation):
    """Concrete frozen rotation animation descriptor."""

    __slots__ = (
        "_role", "_axis", "_travel_rad",
        "_symmetric", "_state_source", "_state_range",
    )

    def __init__(
        self,
        *,
        role: str,
        axis: tuple[float, float, float],
        travel_rad: float,
        symmetric: bool = True,
        state_source: str = "grip_pos",
        state_range: tuple[float, float] = (0.0, 1000.0),
    ) -> None:
        object.__setattr__(self, "_role", role)
        object.__setattr__(self, "_axis", axis)
        object.__setattr__(self, "_travel_rad", travel_rad)
        object.__setattr__(self, "_symmetric", symmetric)
        object.__setattr__(self, "_state_source", state_source)
        object.__setattr__(self, "_state_range", state_range)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("RotationAnimationData is immutable")

    @property
    def role(self) -> str:
        return self._role

    @property
    def axis(self) -> tuple[float, float, float]:
        return self._axis

    @property
    def travel_rad(self) -> float:
        return self._travel_rad

    @property
    def symmetric(self) -> bool:
        return self._symmetric

    @property
    def state_source(self) -> str:
        return self._state_source

    @property
    def state_range(self) -> tuple[float, float]:
        return self._state_range

    def __repr__(self) -> str:
        return (
            f"RotationAnimationData(role={self._role!r}, axis={self._axis}, "
            f"travel_rad={self._travel_rad})"
        )


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
    def animations(self) -> tuple[TranslationAnimation | RotationAnimation, ...]:
        """Animation descriptors for movable tool parts."""
        return ()


class GripperTool(ToolSpec):
    """Contract for gripper tools (``tool_type == ToolType.GRIPPER``).

    ``gripper_type`` selects which gripper panel variant to render.
    """

    @property
    @abstractmethod
    def gripper_type(self) -> GripperType:
        """Gripper sub-type."""
        ...


class ElectricGripperTool(GripperTool):
    """Electric gripper — position/speed/current sliders."""

    @property
    @abstractmethod
    def position_range(self) -> tuple[float, float]:
        """(min, max) position range."""
        ...

    @property
    @abstractmethod
    def speed_range(self) -> tuple[float, float]:
        """(min, max) speed range."""
        ...

    @property
    @abstractmethod
    def current_range(self) -> tuple[int, int]:
        """(min, max) current range in mA."""
        ...


class PneumaticGripperTool(GripperTool):
    """Pneumatic gripper — open/close via I/O port."""

    @property
    @abstractmethod
    def io_port(self) -> int:
        """Digital I/O port number for open/close control."""
        ...


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
