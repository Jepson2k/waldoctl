"""Tool hierarchy — Enums, ABCs, frozen dataclasses, and motion descriptors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Union

from nicegui import binding


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


@binding.bindable_dataclass
class ToolStatus:
    """Universal end-of-arm tool status — the bindable surface exposed at
    ``commander.status.tool``.

    Populated by the host application's status loop at the controller's
    broadcast rate. Consumers combine ``positions[i]`` with
    ``ToolSpec.motions[i]`` to reconstruct the physical state of each DOF
    without knowing the tool type. Tool-specific process data is in
    ``channels``, described by the tool's ``channel_descriptors``.

    Decorated with ``@bindable_dataclass`` so UI elements can bind to leaf
    fields directly: ``bind_text_from(commander.status.tool, "key")``,
    ``bind_value_from(commander.status.tool, "engaged")``, etc. Field
    reassignment by the status loop fires bindings synchronously.

    **Mutate-in-place invariant**: this is a sub-object of ``RobotStatus`` —
    its fields are written individually by the status loop. The instance
    itself is never swapped.
    """

    key: str = "NONE"
    """Attached tool key."""
    variant_key: str = ""
    """Active variant within the attached tool (empty if the tool has no variants)."""
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

    @property
    def position(self) -> float:
        """Primary DOF position (``positions[0]`` if any, else 0.0).

        Convenience accessor for the common single-DOF case (gripper open/
        close, etc.). Not bindable — bind to ``positions`` and use a backward
        function if reactive display of the primary value is needed.
        """
        return self.positions[0] if self.positions else 0.0

    @property
    def current(self) -> float:
        """Primary process-channel value (``channels[0]`` if any, else 0.0).

        Convenience accessor for the common case (e.g. gripper motor current).
        Not bindable — bind to ``channels`` with a backward function for
        reactive display.
        """
        return self.channels[0] if self.channels else 0.0


# ---------------------------------------------------------------------------
# Camera capability — optional camera attached to a tool
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CameraSpec:
    """Default camera attached to a tool.

    The NONE (bare-flange) tool may carry one to act as a workspace
    observer; otherwise this represents a tool-mounted vision system. Users
    can override individual fields per session via :class:`ToolRuntimeSettings`.
    """

    device: int | str = -1
    """OpenCV device index (``int``) or v4l2 device name (``str``).
    ``-1`` means no camera."""
    stream_url: str = "/tool/camera/stream"
    """HTTP endpoint serving an MJPEG stream of the camera feed."""
    width: int = 0
    """Frame width; ``0`` lets the camera service auto-detect."""
    height: int = 0
    """Frame height; ``0`` lets the camera service auto-detect."""


# ---------------------------------------------------------------------------
# Tool runtime settings — user-tweakable overrides on top of the immutable spec
# ---------------------------------------------------------------------------


@binding.bindable_dataclass
class ToolRuntimeSettings:
    """User-tweakable overrides applied on top of a tool's immutable spec.

    Mutable and bindable. Persisted by the host application to per-tool keys
    in :attr:`nicegui.app.storage.general` so users can switch devices /
    settings without reinstalling tools. Tools that need additional override
    fields subclass this and override :meth:`ToolSpec._make_runtime_settings`.

    Default: ``camera_device = None`` means "use the spec's
    ``camera_spec.device``". Setting it to a valid device id overrides.
    """

    camera_device: int | str | None = None


# ---------------------------------------------------------------------------
# Tool specification hierarchy
# ---------------------------------------------------------------------------


class ToolSpec(ABC):
    """Base contract every tool must satisfy.

    ``key`` is unique per tool instance (e.g. ``"pneumatic_left"``).
    ``tool_type`` determines which GUI panel category the tool belongs to.

    Immutable spec fields are stored privately and exposed via read-only
    properties. :attr:`runtime_settings` is the mutable, bindable layer for
    user overrides (currently camera device; tools can extend it).
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
        action_l_labels: tuple[str, str] | None = None,
        action_l_icons: tuple[str, str] | None = None,
        action_l_mode: ToggleMode = ToggleMode.TOGGLE,
        adjust_step: int | None = None,
        adjust_labels: tuple[str, str] | None = None,
        adjust_icons: tuple[str, str] | None = None,
        action_r_labels: tuple[str, str] | None = None,
        action_r_icons: tuple[str, str] | None = None,
        action_r_mode: ToggleMode = ToggleMode.TRIGGER,
        camera_spec: CameraSpec | None = None,
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
        self._action_l_labels = action_l_labels
        self._action_l_icons = action_l_icons
        self._action_l_mode = action_l_mode
        self._adjust_step = adjust_step
        self._adjust_labels = adjust_labels
        self._adjust_icons = adjust_icons
        self._action_r_labels = action_r_labels
        self._action_r_icons = action_r_icons
        self._action_r_mode = action_r_mode
        self._camera_spec = camera_spec
        self._runtime_settings = self._make_runtime_settings()

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
    def action_l_labels(self) -> tuple[str, str] | None:
        """``(off_label, on_label)`` tooltip text for the left action button."""
        return self._action_l_labels

    @property
    def action_l_icons(self) -> tuple[str, str] | None:
        """``(off_icon, on_icon)`` Material Icon names for the left action button."""
        return self._action_l_icons

    @property
    def action_l_mode(self) -> ToggleMode:
        """How the left action button behaves — stateful on/off or one-shot trigger."""
        return self._action_l_mode

    @property
    def adjust_step(self) -> int | None:
        """Step size for the +/- adjust buttons, or ``None`` if not supported."""
        return self._adjust_step

    @property
    def adjust_labels(self) -> tuple[str, str] | None:
        """``(decrease_label, increase_label)`` tooltip text for adjust buttons."""
        return self._adjust_labels

    @property
    def adjust_icons(self) -> tuple[str, str] | None:
        """``(decrease_icon, increase_icon)`` Material Icon names for adjust buttons."""
        return self._adjust_icons

    @property
    def action_r_labels(self) -> tuple[str, str] | None:
        """``(off_label, on_label)`` tooltip text for the right action button."""
        return self._action_r_labels

    @property
    def action_r_icons(self) -> tuple[str, str] | None:
        """``(off_icon, on_icon)`` Material Icon names for the right action button."""
        return self._action_r_icons

    @property
    def action_r_mode(self) -> ToggleMode:
        """How the right action button behaves — stateful on/off or one-shot trigger."""
        return self._action_r_mode

    @property
    def channel_descriptors(self) -> tuple[ChannelDescriptor, ...]:
        """Descriptors for tool-specific process data channels."""
        return ()

    @property
    def camera_spec(self) -> CameraSpec | None:
        """Spec-time default camera attached to this tool, if any.

        Returns ``None`` when the tool has no camera. The user can still
        override via :attr:`runtime_settings`; consumers should resolve the
        effective device via :attr:`effective_camera_device`.
        """
        return self._camera_spec

    @property
    def runtime_settings(self) -> "ToolRuntimeSettings":
        """User-tweakable runtime overrides for this tool.

        Bindable. The host application persists these per tool key to
        :attr:`nicegui.app.storage.general` so user choices survive restarts.
        """
        return self._runtime_settings

    def _make_runtime_settings(self) -> "ToolRuntimeSettings":
        """Construct the per-tool runtime-settings instance.

        Override in subclasses that need additional override fields beyond
        ``camera_device``. The default returns a plain :class:`ToolRuntimeSettings`.
        """
        return ToolRuntimeSettings()

    @property
    def effective_camera_device(self) -> int | str | None:
        """Resolved camera device after applying any runtime override.

        Resolution order: ``runtime_settings.camera_device`` if set, else
        ``camera_spec.device`` if a ``camera_spec`` exists, else ``None``.
        """
        override = self._runtime_settings.camera_device
        if override is not None:
            return override
        return self._camera_spec.device if self._camera_spec else None

    async def action_l(self, engaged: bool) -> None:
        """Left action button handler.

        Override in subclasses to define tool-specific behavior.
        """
        raise NotImplementedError(f"Tool '{self.key}' does not support action_l")

    async def action_r(self, engaged: bool) -> None:
        """Right action button handler.

        Override in subclasses to define tool-specific behavior.
        """
        raise NotImplementedError(f"Tool '{self.key}' does not support action_r")

    async def status(self) -> ToolStatus:
        """Query current tool status from the controller.

        Returns the live tool status (state, engaged, positions, channels).
        Abstract on the base ``ToolSpec``; client-bound tool subclasses
        implement it against the controller.
        """
        raise NotImplementedError


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
        kwargs.setdefault("action_l_labels", ("Close", "Open"))
        kwargs.setdefault("action_l_icons", ("close_fullscreen", "open_in_full"))
        super().__init__(**kwargs)

    @property
    @abstractmethod
    def gripper_type(self) -> GripperType:
        """Gripper sub-type."""
        ...

    @abstractmethod
    async def set_position(self, position: float, **kwargs: float | int) -> int:
        """Set gripper position. 0.0 = fully open, 1.0 = fully closed.

        Category: Tool

        Example:
            rbt.tool.set_position(0.5)
        """
        ...

    async def calibrate(self, **kwargs: object) -> int:
        """Calibrate the gripper. Not all grippers support this.

        Category: Tool

        Example:
            rbt.tool.calibrate()
        """
        raise NotImplementedError

    def is_open(self, position: float) -> bool:
        """Infer open/closed from normalized position. True = open."""
        return position < 0.5

    async def action_l(self, engaged: bool) -> None:
        """Left action: open if engaged, close if not."""
        if engaged:
            await self.open()
        else:
            await self.close()

    @abstractmethod
    async def open(self, **kwargs: float | int) -> int:
        """Open the gripper.

        Category: Tool

        Example:
            rbt.tool.open()
        """
        ...

    @abstractmethod
    async def close(self, **kwargs: float | int) -> int:
        """Close the gripper.

        Category: Tool

        Example:
            rbt.tool.close()
        """
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

    Action methods and computed properties (``adjust_step``,
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
