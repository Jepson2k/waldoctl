# waldoctl — Shared interface definitions for robot arm control

from waldoctl.client import RobotClient
from waldoctl.dry_run import DryRunClient
from waldoctl.joints import (
    HomePosition,
    JointLimits,
    JointsSpec,
    KinodynamicLimits,
    PositionLimits,
)
from waldoctl.results import DryRunResult, DryRunResultData, IKResult, IKResultData
from waldoctl.robot import Robot
from waldoctl.status import PingResult, StatusBuffer, ToolResult
from waldoctl.tools import (
    ElectricGripperTool,
    GripperTool,
    GripperType,
    MeshAnimation,
    PneumaticGripperTool,
    RotationAnimation,
    RotationAnimationData,
    ToolSpec,
    ToolsSpec,
    ToolType,
    TranslationAnimation,
    TranslationAnimationData,
)

__all__ = [
    # Robot + Client ABCs
    "Robot",
    "RobotClient",
    "DryRunClient",
    # Joints (frozen dataclasses)
    "PositionLimits",
    "KinodynamicLimits",
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
    "ToolSpec",
    "GripperTool",
    "ElectricGripperTool",
    "PneumaticGripperTool",
    "ToolsSpec",
    # Animations (ABCs + concrete implementations)
    "MeshAnimation",
    "TranslationAnimation",
    "RotationAnimation",
    "TranslationAnimationData",
    "RotationAnimationData",
]
