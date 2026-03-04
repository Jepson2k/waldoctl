# waldoctl — Shared interface definitions for robot arm control

from waldoctl.client import RobotClient
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
from waldoctl.status import PingResult, StatusBuffer, ToolResult
from waldoctl.tools import (
    ActivationType,
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
    # Status (Protocol + dataclasses)
    "StatusBuffer",
    "PingResult",
    "ToolResult",
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
    "ToolStatus",
    # Mesh + motion descriptors (frozen dataclasses + type alias)
    "MeshSpec",
    "PartMotion",
    "LinearMotion",
    "RotaryMotion",
    "ToolVariant",
]
