"""A sync tool never hands a caller a coroutine, and never hides what the
backend's tool says about itself.

The wrapper used to inherit from the tool it wrapped. Every coroutine the
async base defined then resolved on the wrapper first and came back
un-awaited unless hand-listed — the call looked like it worked, the
gripper never moved — and every property a backend overrode was answered
by the base instead. Both are exercised here through a backend-shaped
tool: one with a verb waldoctl has never heard of, and a property it
computes itself.
"""

from __future__ import annotations

import asyncio
import inspect

from waldoctl.sync_tools import make_sync_tool
from waldoctl.tools import ElectricGripperTool, GripperTool, ToolSpec, ToolStatus

_ZERO_TCP = dict(tcp_origin=(0.0, 0.0, 0.0), tcp_rpy=(0.0, 0.0, 0.0))


class _BackendGripper(ElectricGripperTool):
    """What a backend ships: waldoctl's verbs, plus its own, plus a
    property the base has a default for but the backend computes."""

    def __init__(self) -> None:
        super().__init__(
            key="rec",
            display_name="Recorder",
            tool_type="gripper",
            position_range=(0.0, 1.0),
            speed_range=(0.0, 1.0),
            current_range=(0, 1000),
            **_ZERO_TCP,
        )
        self.calls: list[str] = []

    @property
    def adjust_step(self) -> int | None:
        return 7

    async def set_position(self, position: float, **kwargs: float | int) -> int:
        self.calls.append(f"set_position({position})")
        return 1

    async def calibrate(self, **kwargs: object) -> int:
        self.calls.append("calibrate")
        return 2

    async def open(self, **kwargs: float | int) -> int:
        return 3

    async def close(self, **kwargs: float | int) -> int:
        return 4

    async def status(self) -> ToolStatus:
        self.calls.append("status")
        return ToolStatus(key="rec", engaged=True, positions=(0.25,))

    async def action_r(self, engaged: bool) -> None:
        self.calls.append(f"action_r({engaged})")

    async def stop(self) -> int:
        """A verb no waldoctl base declares."""
        self.calls.append("stop")
        return 9


class _BareTool(ToolSpec):
    """A metadata-only tool, like a flange: no verbs, but ToolSpec's own
    coroutines are still there."""

    def __init__(self) -> None:
        super().__init__(key="bare", display_name="Bare", tool_type="none", **_ZERO_TCP)


def test_every_coroutine_runs_and_every_override_shows_through() -> None:
    tool = _BackendGripper()
    sync = make_sync_tool(tool, asyncio.run)

    # waldoctl's own verbs, the ones it declares but the backend inherits,
    # and the one only the backend has: all plain calls with real results.
    assert sync.set_position(0.5) == 1
    assert sync.calibrate() == 2
    status = sync.status()
    assert not inspect.isawaitable(status)
    assert status.positions == (0.25,)
    assert sync.action_r(False) is None
    assert sync.stop() == 9
    # GripperTool.action_l is inherited on the async side and awaits
    # open(): it must run there, through the wrapper, not come back raw.
    assert sync.action_l(True) is None
    assert tool.calls == [
        "set_position(0.5)",
        "calibrate",
        "status",
        "action_r(False)",
        "stop",
    ]

    # The backend's computed property, not ToolSpec's stored default.
    assert sync.adjust_step == 7
    assert sync.key == "REC"
    assert sync.display_name == "Recorder"

    # Type identity a frontend branches on.
    assert isinstance(sync, ElectricGripperTool)
    assert isinstance(sync, GripperTool)
    assert isinstance(sync, ToolSpec)
    assert isinstance(sync, _BackendGripper)


def test_a_metadata_only_tool_is_wrapped_too() -> None:
    sync = make_sync_tool(_BareTool(), asyncio.run)
    assert isinstance(sync, ToolSpec)
    assert not isinstance(sync, GripperTool)
    # ToolSpec's own coroutines refuse, and the refusal must ARRIVE — as
    # the exception, synchronously — rather than sit inside a coroutine
    # nobody awaits, which is what an unwrapped bare tool handed back.
    for verb, call in (
        ("status", lambda: sync.status()),
        ("action_l", lambda: sync.action_l(True)),
    ):
        try:
            call()
        except NotImplementedError:
            pass
        else:
            raise AssertionError(
                f"{verb} on a bare tool must refuse, not return a coroutine"
            )


def test_every_waldoctl_coroutine_has_a_typed_sync_declaration() -> None:
    """Behaviour is composition, so an undeclared method can only ever be
    UNTYPED, never un-awaited. This keeps 'untyped' from accumulating: a
    coroutine added to a waldoctl tool base must get a sync declaration
    on the matching wrapper, walking the whole MRO — not just the class's
    own __dict__, which is how status and action_r were missed before.
    """
    from waldoctl.sync_tools import (
        SyncElectricGripperTool,
        SyncGripperTool,
        SyncPneumaticGripperTool,
        SyncTool,
    )
    from waldoctl.tools import PneumaticGripperTool

    for async_cls, sync_cls in (
        (ToolSpec, SyncTool),
        (GripperTool, SyncGripperTool),
        (PneumaticGripperTool, SyncPneumaticGripperTool),
        (ElectricGripperTool, SyncElectricGripperTool),
    ):
        for name, _ in inspect.getmembers(async_cls, inspect.iscoroutinefunction):
            declared = inspect.getattr_static(sync_cls, name, None)
            assert declared is not None and not inspect.iscoroutinefunction(declared), (
                f"{async_cls.__name__}.{name} is a coroutine with no typed sync "
                f"declaration on {sync_cls.__name__}: callers see it as Any"
            )
