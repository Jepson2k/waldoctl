"""Tool hierarchy — Enums, ABCs, frozen dataclasses, and motion descriptors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Union


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


class ToolState(IntEnum):
    """State of an end-of-arm tool."""

    OFF = 0
    IDLE = 1
    ACTIVE = 2
    ERROR = 3


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
# Channel descriptors — typed process data channels
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChannelDescriptor:
    """Describes one process data channel reported by a tool.

    The controller populates ``ToolStatus.channels`` positionally — index *i*
    in the channels tuple corresponds to ``channel_descriptors[i]``.
    """

    name: str
    """Human-readable name (e.g. ``"Force"``, ``"Current"``)."""
    unit: str
    """SI unit symbol (e.g. ``"N"``, ``"mA"``, ``"bar"``)."""
    min: float = 0.0
    """Minimum expected value (0 = auto-scale)."""
    max: float = 0.0
    """Maximum expected value (0 = auto-scale)."""


# ---------------------------------------------------------------------------
# Tool status — universal EOAT state
# ---------------------------------------------------------------------------


@dataclass
class ToolStatus:
    """Universal end-of-arm tool status.

    Populated by the controller at the status broadcast rate (50 Hz).
    Consumers combine ``positions[i]`` with ``ToolSpec.motions[i]`` to
    reconstruct the physical state of each DOF without knowing the tool type.
    Tool-specific process data is in ``channels``, described by the tool's
    ``channel_descriptors``.
    """

    key: str = "NONE"
    """Attached tool key."""
    state: ToolState = ToolState.OFF
    """Tool operational state."""
    engaged: bool = False
    """Actively doing work (welding, gripping, dispensing)."""
    part_detected: bool = False
    """EOAT part/object presence confirmed."""
    fault_code: int = 0
    """0=no fault, nonzero=tool-specific error."""
    positions: tuple[float, ...] = ()
    """DOF positions 0..1, one per PartMotion."""
    channels: tuple[float, ...] = ()
    """Tool-specific process data, described by ChannelDescriptor."""


# ---------------------------------------------------------------------------
# Tool specification hierarchy
# ---------------------------------------------------------------------------


class ToolSpec(ABC):
    """Base contract every tool must satisfy.

    ``key`` is unique per tool instance (e.g. ``"pneumatic_left"``).
    ``tool_type`` determines which GUI panel category the tool belongs to.

    All tool configuration is immutable — fields are stored privately
    and exposed via read-only properties.  Action methods (e.g. toggle)
    are abstract — backends provide concrete implementations.
    """

    def __init__(
        self,
        *,
        key: str,
        display_name: str,
        tool_type: ToolType,
        tcp_origin: tuple[float, float, float],
        tcp_rpy: tuple[float, float, float],
        description: str = "",
        meshes: tuple[MeshSpec, ...] = (),
        motions: tuple[PartMotion, ...] = (),
        variants: tuple[ToolVariant, ...] = (),
        activation_type: ActivationType = ActivationType.PROGRESSIVE,
        toggle_labels: tuple[str, str] | None = None,
        toggle_icons: tuple[str, str] | None = None,
        toggle_mode: ToggleMode = ToggleMode.TOGGLE,
        force_jog_step: int | None = None,
    ) -> None:
        self._key = key
        self._display_name = display_name
        self._tool_type = tool_type
        self._tcp_origin = tcp_origin
        self._tcp_rpy = tcp_rpy
        self._description = description
        self._meshes = meshes
        self._motions = motions
        self._variants = variants
        self._activation_type = activation_type
        self._toggle_labels = toggle_labels
        self._toggle_icons = toggle_icons
        self._toggle_mode = toggle_mode
        self._force_jog_step = force_jog_step

    @property
    def key(self) -> str:
        """Unique instance identifier."""
        return self._key

    @property
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        return self._display_name

    @property
    def tool_type(self) -> ToolType:
        """GUI category — determines which panel (if any) is shown."""
        return self._tool_type

    @property
    def tcp_origin(self) -> tuple[float, float, float]:
        """(x, y, z) translation from flange to TCP in meters."""
        return self._tcp_origin

    @property
    def tcp_rpy(self) -> tuple[float, float, float]:
        """(roll, pitch, yaw) orientation from flange to TCP in radians."""
        return self._tcp_rpy

    @property
    def activation_type(self) -> ActivationType:
        """How the tool is activated — binary (on/off) or progressive (continuous)."""
        return self._activation_type

    @property
    def description(self) -> str:
        """Short description of the tool."""
        return self._description

    @property
    def meshes(self) -> tuple[MeshSpec, ...]:
        """Mesh descriptors for 3D visualization."""
        return self._meshes

    @property
    def motions(self) -> tuple[PartMotion, ...]:
        """Physical motion descriptors for movable tool parts."""
        return self._motions

    @property
    def variants(self) -> tuple[ToolVariant, ...]:
        """Named mesh/motion variants (e.g. different jaw sets)."""
        return self._variants

    @property
    def toggle_labels(self) -> tuple[str, str] | None:
        """``(off_label, on_label)`` for toggle tooltip text."""
        return self._toggle_labels

    @property
    def toggle_icons(self) -> tuple[str, str] | None:
        """``(off_icon, on_icon)`` Material Icon names for the toggle button."""
        return self._toggle_icons

    @property
    def toggle_mode(self) -> ToggleMode:
        """How the toggle behaves — stateful on/off or one-shot trigger."""
        return self._toggle_mode

    @property
    def force_jog_step(self) -> int | None:
        """Current/force jog step in mA, or ``None`` if not supported."""
        return self._force_jog_step

    @property
    def channel_descriptors(self) -> tuple[ChannelDescriptor, ...]:
        """Descriptors for tool-specific process data channels."""
        return ()

    async def toggle(self, engaged: bool) -> None:
        """Toggle the tool's primary action based on current engagement state.

        Override in subclasses to define tool-specific toggle behavior.
        """
        raise NotImplementedError(f"Tool '{self.key}' does not support toggle")


# ---------------------------------------------------------------------------
# Gripper hierarchy — tools own their control methods
# ---------------------------------------------------------------------------


class GripperTool(ToolSpec):
    """Base for all grippers.

    All grippers support ``set_position()`` as the universal control method.
    Position is normalized: 0.0 = fully open, 1.0 = fully closed.

    Action methods are abstract — backends provide concrete implementations.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("tool_type", ToolType.GRIPPER)
        kwargs.setdefault("toggle_labels", ("Close", "Open"))
        kwargs.setdefault("toggle_icons", ("close_fullscreen", "open_in_full"))
        super().__init__(**kwargs)

    @property
    @abstractmethod
    def gripper_type(self) -> GripperType:
        """Gripper sub-type."""
        ...

    @abstractmethod
    async def set_position(self, position: float, **kwargs: float | int) -> int:
        """Set gripper position. 0.0 = fully open, 1.0 = fully closed."""
        ...

    async def calibrate(self, **kwargs: object) -> int:
        """Calibrate the gripper. Not all grippers support this."""
        raise NotImplementedError

    def is_open(self, position: float) -> bool:
        """Infer open/closed from normalized position. True = open."""
        return position < 0.5

    async def toggle(self, engaged: bool) -> None:
        """Toggle gripper: open if engaged, close if not."""
        if engaged:
            await self.open()
        else:
            await self.close()

    @abstractmethod
    async def open(self, **kwargs: float | int) -> int:
        """Open the gripper."""
        ...

    @abstractmethod
    async def close(self, **kwargs: float | int) -> int:
        """Close the gripper."""
        ...


class PneumaticGripperTool(GripperTool):
    """Pneumatic gripper — binary open/close.

    Action methods are abstract — backends provide concrete implementations.
    """

    def __init__(self, *, io_port: int, **kwargs: Any) -> None:
        kwargs.setdefault("activation_type", ActivationType.BINARY)
        super().__init__(**kwargs)
        self._io_port = io_port

    @property
    def gripper_type(self) -> GripperType:
        return GripperType.PNEUMATIC

    @property
    def io_port(self) -> int:
        """Digital I/O port number for open/close control."""
        return self._io_port


class ElectricGripperTool(GripperTool):
    """Electric gripper — continuous position with speed and current control.

    Action methods and computed properties (``force_jog_step``,
    ``channel_descriptors``) are abstract — backends provide concrete
    implementations.
    """

    def __init__(
        self,
        *,
        position_range: tuple[float, float],
        speed_range: tuple[float, float],
        current_range: tuple[int, int],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._position_range = position_range
        self._speed_range = speed_range
        self._current_range = current_range

    @property
    def gripper_type(self) -> GripperType:
        return GripperType.ELECTRIC

    @property
    def position_range(self) -> tuple[float, float]:
        """(min, max) position range (normalized 0..1)."""
        return self._position_range

    @property
    def speed_range(self) -> tuple[float, float]:
        """(min, max) speed range (normalized 0..1)."""
        return self._speed_range

    @property
    def current_range(self) -> tuple[int, int]:
        """(min, max) current range in mA."""
        return self._current_range


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
