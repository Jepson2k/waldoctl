"""The sync facade must never hand a caller a coroutine.

``make_sync_tool`` exists so a synchronous script can drive a tool. Any public
async verb the wrapper forgets to override falls through ``__getattr__`` to the
async implementation, and calling it builds a coroutine nobody awaits: no
datagram is sent and the only symptom is a RuntimeWarning. For ``stop()`` that
means the jaws keep travelling.
"""

from __future__ import annotations

import asyncio
import inspect

from waldoctl import ElectricGripperTool, ToolStatus
from waldoctl.sync_tools import make_sync_tool


class _Gripper(ElectricGripperTool):
    """A concrete electric gripper whose verbs record the call and answer with
    a distinct value, so the test can tell a forwarded call from a leaked
    coroutine."""

    def __init__(self) -> None:
        super().__init__(
            key="grip",
            display_name="Grip",
            tool_type="gripper",
            tcp_origin=(0.0, 0.0, 0.0),
            tcp_rpy=(0.0, 0.0, 0.0),
            position_range=(0.0, 1.0),
            speed_range=(0.0, 1.0),
            current_range=(0, 1000),
        )
        self.calls: list[str] = []

    async def set_position(self, position: float, **kwargs: float | int) -> int:
        self.calls.append("set_position")
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

    async def stop(self, **kwargs: object) -> int:
        self.calls.append("stop")
        return 5

    async def release(self, **kwargs: object) -> int:
        self.calls.append("release")
        return 6

    async def action_r(self, engaged: bool) -> None:
        self.calls.append("action_r")

    async def status(self) -> ToolStatus:
        self.calls.append("status")
        return ToolStatus(key="GRIP", engaged=True)


def _public_coroutine_verbs(tool: object) -> list[str]:
    return sorted(
        name
        for name, member in inspect.getmembers(type(tool))
        if not name.startswith("_") and inspect.iscoroutinefunction(member)
    )


def test_every_async_verb_is_synchronous_on_the_wrapper() -> None:
    tool = _Gripper()
    sync = make_sync_tool(tool, asyncio.run)

    verbs = _public_coroutine_verbs(tool)
    assert {"stop", "release", "status", "action_l", "action_r"} <= set(verbs)
    leaked = [v for v in verbs if inspect.iscoroutinefunction(getattr(sync, v))]
    assert leaked == [], f"the wrapper hands back coroutines for {leaked}"

    assert sync.set_position(0.5) == 1
    assert sync.calibrate() == 2
    assert sync.open() == 3
    assert sync.close() == 4
    assert sync.stop() == 5
    assert sync.release() == 6
    assert sync.action_l(True) is None
    assert sync.action_r(True) is None
    status = sync.status()
    assert isinstance(status, ToolStatus)
    assert status.engaged
    assert tool.calls == [
        "set_position",
        "calibrate",
        "open",
        "close",
        "stop",
        "release",
        "open",
        "action_r",
        "status",
    ]
