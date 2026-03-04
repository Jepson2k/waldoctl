"""Synchronous tool wrappers — per-type, mirrors the sync/async client split.

Each wrapper inherits from its async counterpart so ``isinstance`` checks
work on both sides.  Abstract properties are redeclared as one-liner
delegations; action methods wrap the async version with the caller-supplied
``run`` function (typically ``parol6.client.sync_client._run``).
"""

from __future__ import annotations

from typing import Callable

from waldoctl.tools import (
    ElectricGripperTool,
    GripperTool,
    GripperType,
    PneumaticGripperTool,
    ToolSpec,
    ToolType,
)


# ---------------------------------------------------------------------------
# SyncGripperTool
# ---------------------------------------------------------------------------


class SyncGripperTool(GripperTool):
    """Sync wrapper for any ``GripperTool``."""

    def __init__(self, async_tool: GripperTool, run: Callable) -> None:
        self._async = async_tool
        self._run = run

    # -- abstract property delegations --

    @property
    def key(self) -> str:
        return self._async.key

    @property
    def display_name(self) -> str:
        return self._async.display_name

    @property
    def tool_type(self) -> ToolType:
        return self._async.tool_type

    @property
    def tcp_origin(self) -> tuple[float, float, float]:
        return self._async.tcp_origin

    @property
    def tcp_rpy(self) -> tuple[float, float, float]:
        return self._async.tcp_rpy

    @property
    def gripper_type(self) -> GripperType:
        return self._async.gripper_type

    # -- action methods --

    def set_position(self, position: float, **kwargs: object) -> int:  # type: ignore[override]
        return self._run(self._async.set_position(position, **kwargs))

    def open(self, **kwargs: object) -> int:  # type: ignore[override]
        return self._run(self._async.open(**kwargs))

    def close(self, **kwargs: object) -> int:  # type: ignore[override]
        return self._run(self._async.close(**kwargs))

    def calibrate(self, **kwargs: object) -> int:  # type: ignore[override]
        return self._run(self._async.calibrate(**kwargs))


# ---------------------------------------------------------------------------
# SyncPneumaticGripperTool
# ---------------------------------------------------------------------------


class SyncPneumaticGripperTool(PneumaticGripperTool):
    """Sync wrapper for ``PneumaticGripperTool``."""

    def __init__(self, async_tool: PneumaticGripperTool, run: Callable) -> None:
        self._async = async_tool
        self._run = run

    @property
    def key(self) -> str:
        return self._async.key

    @property
    def display_name(self) -> str:
        return self._async.display_name

    @property
    def tool_type(self) -> ToolType:
        return self._async.tool_type

    @property
    def tcp_origin(self) -> tuple[float, float, float]:
        return self._async.tcp_origin

    @property
    def tcp_rpy(self) -> tuple[float, float, float]:
        return self._async.tcp_rpy

    @property
    def gripper_type(self) -> GripperType:
        return self._async.gripper_type

    @property
    def io_port(self) -> int:
        return self._async.io_port

    def set_position(self, position: float, **kwargs: object) -> int:  # type: ignore[override]
        return self._run(self._async.set_position(position, **kwargs))

    def open(self, **kwargs: object) -> int:  # type: ignore[override]
        return self._run(self._async.open(**kwargs))

    def close(self, **kwargs: object) -> int:  # type: ignore[override]
        return self._run(self._async.close(**kwargs))


# ---------------------------------------------------------------------------
# SyncElectricGripperTool
# ---------------------------------------------------------------------------


class SyncElectricGripperTool(ElectricGripperTool):
    """Sync wrapper for ``ElectricGripperTool``."""

    def __init__(self, async_tool: ElectricGripperTool, run: Callable) -> None:
        self._async = async_tool
        self._run = run

    @property
    def key(self) -> str:
        return self._async.key

    @property
    def display_name(self) -> str:
        return self._async.display_name

    @property
    def tool_type(self) -> ToolType:
        return self._async.tool_type

    @property
    def tcp_origin(self) -> tuple[float, float, float]:
        return self._async.tcp_origin

    @property
    def tcp_rpy(self) -> tuple[float, float, float]:
        return self._async.tcp_rpy

    @property
    def gripper_type(self) -> GripperType:
        return self._async.gripper_type

    @property
    def position_range(self) -> tuple[float, float]:
        return self._async.position_range

    @property
    def speed_range(self) -> tuple[float, float]:
        return self._async.speed_range

    @property
    def current_range(self) -> tuple[int, int]:
        return self._async.current_range

    def set_position(self, position: float, **kwargs: object) -> int:  # type: ignore[override]
        return self._run(self._async.set_position(position, **kwargs))

    def calibrate(self, **kwargs: object) -> int:  # type: ignore[override]
        return self._run(self._async.calibrate(**kwargs))


# ---------------------------------------------------------------------------
# Dispatch helper
# ---------------------------------------------------------------------------

_SYNC_MAP: dict[type, type] = {
    PneumaticGripperTool: SyncPneumaticGripperTool,
    ElectricGripperTool: SyncElectricGripperTool,
    GripperTool: SyncGripperTool,
}


def make_sync_tool(async_tool: ToolSpec, run: Callable) -> ToolSpec:
    """Wrap an async-bound tool in the matching sync wrapper.

    Returns the tool as-is for metadata-only tools (no action methods).
    """
    for async_cls, sync_cls in _SYNC_MAP.items():
        if isinstance(async_tool, async_cls):
            return sync_cls(async_tool, run)
    return async_tool
