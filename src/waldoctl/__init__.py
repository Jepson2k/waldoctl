# waldoctl — Shared interface definitions for robot arm control

from importlib.metadata import version as _get_version

__version__ = _get_version("waldoctl")

from waldoctl.client import RobotClient
from waldoctl.discovery import (
    available_backends,
    list_backends,
    load_robot_class,
)
from waldoctl.dry_run import DryRunClient
from waldoctl.joints import (
    CartesianKinodynamicLimits,
    HomePosition,
    JointLimits,
    JointsSpec,
    KinodynamicLimits,
    LinearAngularLimits,
    PositionLimits,
)
from waldoctl.results import DryRunResult, DryRunResultData, IKResult, IKResultData
from waldoctl.robot import Robot
from waldoctl.status import (
    ActionState,
    ActivityResult,
    PingResult,
    StatusBuffer,
    ToolResult,
)
from waldoctl.types import Axis, Frame
from waldoctl.tools import (
    ActivationType,
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
    ToolSpec,
    ToolsSpec,
    ToolState,
    ToolStatus,
    ToolType,
    ToolVariant,
)

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
]
