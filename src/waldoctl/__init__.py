# waldoctl — Shared interface definitions for robot arm control

from importlib.metadata import version as _get_version

from waldoctl._commander import Commander
from waldoctl.client import RobotClient
from waldoctl.discovery import (
    available_backends,
    list_backends,
    load_robot_class,
)
from waldoctl.dry_run import DryRunClient
from waldoctl.dry_run_state import (
    DryRun,
    PathSegment,
    Playback,
    ProgramTarget,
    ToolAction,
    ToolSelection,
)
from waldoctl.joints import (
    CartesianKinodynamicLimits,
    HomePosition,
    JointLimits,
    JointsSpec,
    KinodynamicLimits,
    LinearAngularLimits,
    PositionLimits,
)
from waldoctl.programs import (
    EditFlow,
    EditId,
    Execution,
    LogEntry,
    PendingEdit,
    Program,
    ProgramLog,
    ProgramTabs,
    RecordedProgram,
    Recording,
)
from waldoctl.results import DryRunResult, DryRunResultData, IKResult, IKResultData
from waldoctl.robot import Robot
from waldoctl.notify import ChangeNotifierMixin
from waldoctl.robot_status import (
    IO,
    Action,
    ActionLogEntry,
    ActionStatus,
    AngleArray,
    CartesianJogAvailability,
    FrameJogAvailability,
    Joints,
    Pose,
    RobotStatus,
    ToolTimeSeries,
)
from waldoctl.settings import (
    EnvelopeMode,
    GripperSettings,
    JogSettings,
    PluginConfig,
    Settings,
    ViewSettings,
)
from waldoctl.status import (
    ActionState,
    ActivityResult,
    PingResult,
    StatusBuffer,
    ToolResult,
)
from waldoctl.tools import (
    ActivationType,
    CameraSpec,
    ChannelDescriptor,
    ElectricGripperTool,
    GripperTool,
    GripperType,
    LinearMotion,
    MeshRole,
    MeshSpec,
    PartMotion,
    PneumaticGripperTool,
    RotaryMotion,
    ToggleMode,
    ToolRuntimeSettings,
    ToolSpec,
    ToolsSpec,
    ToolState,
    ToolStatus,
    ToolType,
    ToolVariant,
)
from waldoctl.types import Axis, Frame

__version__ = _get_version("waldoctl")


# ---------------------------------------------------------------------------
# Commander locator (PEP 562 module-level __getattr__)
# ---------------------------------------------------------------------------
# `waldoctl.commander` is typed as `Commander` (non-Optional). The host
# application registers a live instance via `_set_commander` during startup;
# accessing `commander` before then raises `RuntimeError` with a clear message.
# Same shape as Flask's `current_app` or NiceGUI's `app.storage`: consumers
# never write `if commander is not None`.

_commander_instance: Commander | None = None  # private slot; do not access directly


def _set_commander(c: Commander) -> None:
    """Register the live ``Commander`` instance. Host application calls this
    once during startup, after every sub-handle is constructed."""
    global _commander_instance
    _commander_instance = c


def _clear_commander() -> None:
    """Drop the live ``Commander`` reference. Host application calls this on
    shutdown so subsequent access raises a fresh initialisation error."""
    global _commander_instance
    _commander_instance = None


def __getattr__(name: str):
    """Resolve ``waldoctl.commander`` lazily; raise clearly when unset."""
    if name == "commander":
        if _commander_instance is None:
            raise RuntimeError(
                "waldoctl.commander not initialised — host application's "
                "startup hasn't called waldoctl._set_commander(...) yet"
            )
        return _commander_instance
    raise AttributeError(f"module 'waldoctl' has no attribute {name!r}")


# Type-only declaration so dotted access `waldoctl.commander` is typed as
# `Commander` (non-Optional) under static analysis. Runtime resolution goes
# through `__getattr__` — always use dotted access, never `from waldoctl import
# commander`, which would resolve the locator at import time before the host
# has installed the Commander.
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    commander: Commander


__all__ = [
    # Robot + Client ABCs / Protocols
    "Robot",
    "RobotClient",
    "DryRunClient",
    # Joints (frozen dataclasses)
    "PositionLimits",
    "KinodynamicLimits",
    "LinearAngularLimits",
    "CartesianKinodynamicLimits",
    "JointLimits",
    "HomePosition",
    "JointsSpec",
    # Results (Protocols + dataclasses)
    "IKResult",
    "DryRunResult",
    "IKResultData",
    "DryRunResultData",
    # Status (Protocol + dataclasses + enums)
    "StatusBuffer",
    "PingResult",
    "ToolResult",
    "ActionState",
    "ActivityResult",
    # Tools (enums + ABCs)
    "ToolType",
    "GripperType",
    "ActivationType",
    "ToggleMode",
    "MeshRole",
    "ToolSpec",
    "GripperTool",
    "ElectricGripperTool",
    "PneumaticGripperTool",
    "ToolsSpec",
    "ToolState",
    "ToolStatus",
    "ChannelDescriptor",
    "CameraSpec",
    "ToolRuntimeSettings",
    # Type aliases
    "Frame",
    "Axis",
    # Discovery
    "available_backends",
    "list_backends",
    "load_robot_class",
    # Version
    "__version__",
    # Mesh + motion descriptors (frozen dataclasses + type alias)
    "MeshSpec",
    "PartMotion",
    "LinearMotion",
    "RotaryMotion",
    "ToolVariant",
    # Commander locator
    "Commander",
    # Robot status surface
    "RobotStatus",
    "Pose",
    "Joints",
    "FrameJogAvailability",
    "CartesianJogAvailability",
    "IO",
    "Action",
    "ActionLogEntry",
    "ActionStatus",
    "AngleArray",
    "ToolTimeSeries",
    "ChangeNotifierMixin",
    # Programs surface
    "ProgramTabs",
    "Program",
    "ProgramLog",
    "LogEntry",
    "Execution",
    "Recording",
    "RecordedProgram",
    "EditFlow",
    "EditId",
    "PendingEdit",
    # Dry-run surface
    "DryRun",
    "Playback",
    "ProgramTarget",
    "PathSegment",
    "ToolAction",
    "ToolSelection",
    # Settings surface
    "Settings",
    "JogSettings",
    "GripperSettings",
    "ViewSettings",
    "PluginConfig",
    "EnvelopeMode",
]
