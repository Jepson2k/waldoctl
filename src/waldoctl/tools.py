"""Tool hierarchy — Enums, ABCs, frozen dataclasses, and motion descriptors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Union

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


class ActivationType(Enum):
    """How a tool is activated / controlled.

    BINARY:      On/off only — no intermediate position feedback from hardware.
                 Tools with motion descriptors need ``estimated_speed`` fields
                 so the simulator can animate transitions.
    PROGRESSIVE: Continuous position control with real-time position feedback.
    """

    BINARY = "binary"
    PROGRESSIVE = "progressive"


class ToggleMode(Enum):
    """How a tool's quick-action toggle behaves on the control panel."""

    TOGGLE = "toggle"
    """Stateful on/off (grippers open/close, vacuum on/off)."""
    TRIGGER = "trigger"
    """One-shot cycle start (dispensers, welders)."""


# ---------------------------------------------------------------------------
# Mesh description types
# ---------------------------------------------------------------------------


class MeshRole(Enum):
    """Well-defined roles for tool mesh groups."""

    BODY = "body"
    """Static structural part."""
    JAW = "jaw"
    """Translating gripper jaw."""
    SPINDLE = "spindle"
    """Rotating part (drill bit, mill bit, etc.)."""


@dataclass(frozen=True)
class MeshSpec:
    """Immutable descriptor for a single STL mesh in a tool assembly."""

    file: str
    """Filename of the STL mesh."""
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """(x, y, z) offset in meters."""
    rpy: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """(roll, pitch, yaw) orientation in radians."""
    role: MeshRole = MeshRole.BODY
    """Which mesh group this belongs to."""


# ---------------------------------------------------------------------------
# Motion descriptors — physical degrees of freedom on tool parts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LinearMotion:
    """Linear motion of tool parts (gripper jaws, press-fit rams)."""

    role: MeshRole
    """Which mesh group moves."""
    axis: tuple[float, float, float]
    """Unit vector along which the motion occurs."""
    travel_m: float
    """Max displacement per side in meters."""
    symmetric: bool = True
    """If True, paired parts (left/right) move in opposite directions."""
    estimated_speed_m_s: float | None = None
    """Estimated travel speed in m/s (for binary-activation tools without position feedback)."""
    estimated_accel_m_s2: float | None = None
    """Estimated acceleration in m/s² (for binary-activation tools)."""


@dataclass(frozen=True)
class RotaryMotion:
    """Rotary motion of tool parts (spindle bits, drill chucks)."""

    role: MeshRole
    """Which mesh group moves."""
    axis: tuple[float, float, float]
    """Unit vector for the rotation axis."""
    travel_rad: float
    """Max rotation in radians."""
    symmetric: bool = True
    """If True, paired parts rotate in opposite directions."""
    estimated_speed_rad_s: float | None = None
    """Estimated angular speed in rad/s (for binary-activation tools)."""
    estimated_accel_rad_s2: float | None = None
    """Estimated angular acceleration in rad/s² (for binary-activation tools)."""


PartMotion = Union[LinearMotion, RotaryMotion]
"""Type alias for any motion descriptor."""


@dataclass(frozen=True)
class ToolVariant:
    """Named variant that replaces a tool's meshes and motions.

    Each variant is self-contained — it provides a complete set of meshes
    and motions, so the scene swaps them wholesale without merge logic.
    """

    key: str
    """Unique identifier within the tool (e.g. ``"finger"``, ``"pinch"``)."""
    display_name: str
    """Human-readable name for the UI dropdown."""
    meshes: tuple[MeshSpec, ...] = ()
    """Complete mesh set for this variant."""
    motions: tuple[PartMotion, ...] = ()
    """Complete motion descriptors for this variant."""
    tcp_origin: tuple[float, float, float] | None = None
    """(x, y, z) TCP translation in meters, or None to use tool default."""
    tcp_rpy: tuple[float, float, float] | None = None
    """(roll, pitch, yaw) TCP orientation in radians, or None to use tool default."""


# ---------------------------------------------------------------------------
# Tool status — universal EOAT state
# ---------------------------------------------------------------------------


@dataclass
class ToolStatus:
    """Universal end-of-arm tool status.

    Populated by the controller at the status broadcast rate (50 Hz).
    Consumers combine ``positions[i]`` with ``ToolSpec.motions[i]`` to
    reconstruct the physical state of each DOF without knowing the tool type.
    """

    key: str = "NONE"
    """Attached tool key."""
    state: int = 0
    """0=off, 1=idle, 2=active, 3=error."""
    engaged: bool = False
    """Actively doing work (welding, gripping, dispensing)."""
    part_detected: bool = False
    """EOAT part/object presence confirmed."""
    force: float = 0.0
    """Force measurement (N)."""
    pressure: float = 0.0
    """Pressure measurement (bar)."""
    process_value: float = 0.0
    """Main process metric — meaning is tool-specific:
    torque (driver), current (welder), flow (dispenser), RPM (spindle)."""
    positions: tuple[float, ...] = ()
    """DOF positions 0..1, one per PartMotion."""
    cycle_complete: bool = False
    """A discrete cycle just finished."""
    cycle_result: int = 0
    """0=none, 1=pass, 2=fail."""
    fault_code: int = 0
    """0=no fault, nonzero=tool-specific error."""


# ---------------------------------------------------------------------------
# Tool specification hierarchy
# ---------------------------------------------------------------------------


class ToolSpec(ABC):
    """Base contract every tool must satisfy.

    ``key`` is unique per tool instance (e.g. ``"pneumatic_left"``).
    ``tool_type`` determines which GUI panel category the tool belongs to.

    Action methods dispatch through ``_cmd()`` → ``_execute``.  Tools are
    bound to a client by setting ``_execute`` to the client's
    ``tool_action`` method (typically via shallow copy at client creation).
    """

    _execute: Callable[..., Any] | None = None

    async def _cmd(
        self, action: str, params: list[Any] | None = None, **kwargs: object
    ) -> int:
        """Dispatch a command through the bound client."""
        if self._execute is None:
            raise RuntimeError(
                "Tool not bound to a client. Access via client.tool."
            )
        return await self._execute(self.key, action, params or [], **kwargs)

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
    def activation_type(self) -> ActivationType:
        """How the tool is activated — binary (on/off) or progressive (continuous)."""
        return ActivationType.PROGRESSIVE

    @property
    def description(self) -> str:
        """Short description of the tool."""
        return ""

    @property
    def meshes(self) -> tuple[MeshSpec, ...]:
        """Mesh descriptors for 3D visualization."""
        return ()

    @property
    def motions(self) -> tuple[PartMotion, ...]:
        """Physical motion descriptors for movable tool parts."""
        return ()

    @property
    def variants(self) -> tuple[ToolVariant, ...]:
        """Named mesh/motion variants (e.g. different jaw sets)."""
        return ()

    # -- Quick-action properties for control panel ---

    @property
    def toggle_labels(self) -> tuple[str, str] | None:
        """``(off_label, on_label)`` for toggle tooltip text.

        Return ``None`` if the tool has no quick toggle action.
        """
        return None

    @property
    def toggle_icons(self) -> tuple[str, str] | None:
        """``(off_icon, on_icon)`` Material Icon names for the toggle button.

        Return ``None`` if the tool has no quick toggle action.
        """
        return None

    @property
    def toggle_mode(self) -> ToggleMode:
        """How the toggle behaves — stateful on/off or one-shot trigger."""
        return ToggleMode.TOGGLE

    @property
    def force_jog_step(self) -> int | None:
        """Current/force jog step in mA, or ``None`` if not supported."""
        return None


# ---------------------------------------------------------------------------
# Gripper hierarchy — tools own their control methods
# ---------------------------------------------------------------------------


class GripperTool(ToolSpec):
    """Base for all grippers.

    All grippers support ``set_position()`` as the universal control method.
    Position is normalized: 0.0 = fully open, 1.0 = fully closed.

    Action methods are concrete and dispatch through ``_cmd()``.
    Bind to a client (``_execute``) before calling.
    """

    @property
    @abstractmethod
    def gripper_type(self) -> GripperType:
        """Gripper sub-type."""
        ...

    async def set_position(self, position: float, **kwargs: object) -> int:
        """Set gripper position. 0.0 = fully open, 1.0 = fully closed."""
        speed = float(kwargs.get("speed", 0.5))
        current = int(kwargs.get("current", 500))
        return await self._cmd("move", [position, speed, current])

    async def calibrate(self, **kwargs: object) -> int:
        """Calibrate the gripper. Not all grippers support this."""
        return await self._cmd("calibrate")

    # -- Quick-action overrides ---

    @property
    def toggle_labels(self) -> tuple[str, str]:
        return ("Close", "Open")

    @property
    def toggle_icons(self) -> tuple[str, str]:
        return ("close_fullscreen", "open_in_full")

    def is_open(self, position: float) -> bool:
        """Infer open/closed from normalized position. True = open."""
        return position < 0.5


class PneumaticGripperTool(GripperTool):
    """Pneumatic gripper — binary open/close.

    ``set_position()`` clamps to binary and delegates to ``open()``/``close()``.
    """

    @property
    def activation_type(self) -> ActivationType:
        return ActivationType.BINARY

    @property
    @abstractmethod
    def io_port(self) -> int:
        """Digital I/O port number for open/close control."""
        ...

    async def set_position(self, position: float, **kwargs: object) -> int:
        """Binary position: < 0.5 opens, >= 0.5 closes."""
        if position < 0.5:
            return await self.open(**kwargs)
        return await self.close(**kwargs)

    async def open(self, **kwargs: object) -> int:
        """Open the gripper."""
        return await self._cmd("open")

    async def close(self, **kwargs: object) -> int:
        """Close the gripper."""
        return await self._cmd("close")


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

    async def set_position(self, position: float, **kwargs: object) -> int:
        """Set position with speed and current control."""
        speed = float(kwargs.get("speed", 0.5))
        current = int(kwargs.get("current", self.current_range[0]))
        return await self._cmd("move", [position, speed, current])

    async def calibrate(self, **kwargs: object) -> int:
        """Calibrate the electric gripper."""
        return await self._cmd("calibrate")

    @property
    def force_jog_step(self) -> int:
        """Default current step: ~10% of range, rounded to nearest 10 mA."""
        lo, hi = self.current_range
        return max(10, round((hi - lo) / 10 / 10) * 10)


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
