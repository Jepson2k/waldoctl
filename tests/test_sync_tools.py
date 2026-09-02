"""A sync tool must not hand back coroutines.

The wrappers spell out the gripper's motion methods, but a tool's async
API is wider than that — ``status``, ``action_l``, ``action_r``. Those
reach the caller through ``__getattr__``, and returning the bound async
method there gives back an un-awaited coroutine: the call appears to
succeed, the hardware never moves, and the only trace is a
"coroutine was never awaited" warning.
"""

from __future__ import annotations

import inspect

from waldoctl.sync_tools import make_sync_tool
from waldoctl.tools import ElectricGripperTool, ToolStatus


class _Recording(ElectricGripperTool):
    def __init__(self) -> None:
        super().__init__(
            key="rec",
            display_name="Recorder",
            tool_type="gripper",
            tcp_origin=(0.0, 0.0, 0.0),
            tcp_rpy=(0.0, 0.0, 0.0),
            position_range=(0.0, 1.0),
            speed_range=(0.0, 1.0),
            current_range=(0, 1000),
        )
        self.calls: list[str] = []

    async def set_position(self, position: float, **kwargs: float | int) -> int:
        self.calls.append(f"set_position({position})")
        return 1

    async def calibrate(self, **kwargs: object) -> int:
        self.calls.append("calibrate")
        return 2

    async def open(self, **kwargs: float | int) -> int:
        self.calls.append("open")
        return 3

    async def close(self, **kwargs: float | int) -> int:
        self.calls.append("close")
        return 4

    async def status(self) -> ToolStatus:
        self.calls.append("status")
        return ToolStatus(key="rec", engaged=True, positions=(0.25,))

    async def action_l(self, engaged: bool) -> None:
        self.calls.append(f"action_l({engaged})")

    async def action_r(self, engaged: bool) -> None:
        self.calls.append(f"action_r({engaged})")


def test_every_async_tool_method_runs_when_called_on_the_sync_wrapper() -> None:
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        _exercise(make_sync_tool(_Recording(), loop.run_until_complete))
    finally:
        loop.close()


def _exercise(sync: object) -> None:
    tool = sync._async  # type: ignore[attr-defined]

    assert sync.set_position(0.5) == 1
    assert sync.calibrate() == 2

    # Inherited from the async base rather than a plain delegation.
    status = sync.status()
    assert not inspect.isawaitable(status), "status() handed back a coroutine"
    assert status.positions == (0.25,)
    assert sync.action_l(True) is None
    assert sync.action_r(False) is None

    assert tool.calls == [
        "set_position(0.5)",
        "calibrate",
        "status",
        "action_l(True)",
        "action_r(False)",
    ]

    # Non-callable attributes still pass straight through.
    assert sync.key == "REC"
    assert sync.display_name == "Recorder"


def test_no_async_method_reaches_a_caller_unwrapped() -> None:
    """Every coroutine method on an async tool is overridden on its sync
    wrapper.

    The wrappers subclass their async counterparts, so an async method
    they do not override is INHERITED — ``__getattr__`` never runs for it
    and the caller gets a coroutine back. Adding a method to a tool base
    without adding it here is the way that happens, so this is checked
    rather than remembered.
    """
    from waldoctl.sync_tools import (
        SyncElectricGripperTool,
        SyncGripperTool,
        SyncPneumaticGripperTool,
    )
    from waldoctl.tools import GripperTool, PneumaticGripperTool

    for sync_cls, async_cls in (
        (SyncGripperTool, GripperTool),
        (SyncPneumaticGripperTool, PneumaticGripperTool),
        (SyncElectricGripperTool, ElectricGripperTool),
    ):
        for name, attr in vars(async_cls).items():
            if not inspect.iscoroutinefunction(attr):
                continue
            wrapped = getattr(sync_cls, name, None)
            assert wrapped is not None and not inspect.iscoroutinefunction(wrapped), (
                f"{sync_cls.__name__}.{name} is still the async {async_cls.__name__} "
                f"method, so calling it returns an un-awaited coroutine"
            )
