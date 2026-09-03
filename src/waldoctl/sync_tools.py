"""Synchronous tool wrappers — mirrors the sync/async client split.

A sync tool is the async tool behind a ``run`` function (the sync
client's loop runner): every coroutine method comes back as a plain call,
everything else is the async tool's own attribute.

Two jobs, split deliberately. BEHAVIOUR is composition: the wrapper
holds the async tool and forwards every attribute through
``__getattr__``, running coroutines through ``run`` — so a verb only a
backend declares, or a property a backend overrides, is served correctly
without anyone listing it here. TYPING is declaration: the three
``Sync*`` classes spell out the sync signatures of the verbs waldoctl
itself defines, so a typed caller sees ``open() -> int`` rather than a
coroutine. A method missing from the declarations is merely untyped;
it can never come back un-awaited. ``isinstance`` against the async ABCs
holds by registering each wrapper class with them.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, overload

from waldoctl.tools import (
    ElectricGripperTool,
    GripperTool,
    GripperType,
    PneumaticGripperTool,
    ToolSpec,
    ToolStatus,
)

_RUNNER_FIELDS = frozenset({"_async", "_run"})


class SyncTool:
    """The async tool behind ``run``.

    Attribute access forwards to the wrapped tool. A coroutine method is
    returned as a callable that runs it to completion through ``run``;
    every other attribute — properties, plain methods, data — is the
    async tool's own, so a backend's overrides are what the caller sees.
    """

    def __init__(self, async_tool: ToolSpec, run: Callable[[Any], Any]) -> None:
        self._async = async_tool
        self._run = run

    def __getattr__(self, name: str) -> Any:
        # Only reached for names not on the wrapper itself. The two fields
        # set in __init__ are excluded so a lookup before __init__ (copy,
        # pickle) raises instead of recursing.
        if name in _RUNNER_FIELDS:
            raise AttributeError(name)
        attr = getattr(self._async, name)
        if inspect.iscoroutinefunction(attr):
            run = self._run

            def call(*args: Any, **kwargs: Any) -> Any:
                return run(attr(*args, **kwargs))

            call.__name__ = name
            call.__doc__ = attr.__doc__
            return call
        return attr

    def __repr__(self) -> str:
        return f"Sync({self._async!r})"

    # ToolSpec's own coroutines, typed. Bodies delegate the same way
    # __getattr__ would; the declarations exist for the type checker.

    def status(self) -> ToolStatus:
        return self._run(self._async.status())

    def action_l(self, engaged: bool) -> None:
        return self._run(self._async.action_l(engaged))

    def action_r(self, engaged: bool) -> None:
        return self._run(self._async.action_r(engaged))

    # Metadata a caller reads most, typed rather than Any.

    @property
    def key(self) -> str:
        return self._async.key

    @property
    def display_name(self) -> str:
        return self._async.display_name

    @property
    def tool_type(self) -> str:
        return self._async.tool_type

    @property
    def tcp_origin(self) -> tuple[float, float, float]:
        return self._async.tcp_origin

    @property
    def tcp_rpy(self) -> tuple[float, float, float]:
        return self._async.tcp_rpy


class SyncGripperTool(SyncTool):
    """Sync view of any ``GripperTool``."""

    _async: GripperTool

    @property
    def gripper_type(self) -> GripperType:
        return self._async.gripper_type

    def set_position(self, position: float, **kwargs: float | int) -> int:
        return self._run(self._async.set_position(position, **kwargs))

    def open(self, **kwargs: float | int) -> int:
        return self._run(self._async.open(**kwargs))

    def close(self, **kwargs: float | int) -> int:
        return self._run(self._async.close(**kwargs))

    def calibrate(self, **kwargs: object) -> int:
        return self._run(self._async.calibrate(**kwargs))


class SyncPneumaticGripperTool(SyncGripperTool):
    """Sync view of a ``PneumaticGripperTool``."""

    _async: PneumaticGripperTool

    @property
    def io_port(self) -> int:
        return self._async.io_port


class SyncElectricGripperTool(SyncGripperTool):
    """Sync view of an ``ElectricGripperTool``."""

    _async: ElectricGripperTool

    @property
    def position_range(self) -> tuple[float, float]:
        return self._async.position_range

    @property
    def speed_range(self) -> tuple[float, float]:
        return self._async.speed_range

    @property
    def current_range(self) -> tuple[int, int]:
        return self._async.current_range


# Most specific typed wrapper for each async ABC, checked in this order.
_TYPED: tuple[tuple[type, type[SyncTool]], ...] = (
    (ElectricGripperTool, SyncElectricGripperTool),
    (PneumaticGripperTool, SyncPneumaticGripperTool),
    (GripperTool, SyncGripperTool),
    (ToolSpec, SyncTool),
)

_WRAPPERS: dict[type, type[SyncTool]] = {}


def _wrapper_for(tool_cls: type) -> type[SyncTool]:
    """The wrapper class standing in for ``tool_cls``: the typed ``Sync*``
    for its nearest waldoctl ABC, specialised once per concrete async
    class and registered with every ``ToolSpec`` ABC in that class's MRO —
    the concrete class included — so ``isinstance(sync, X)`` answers as it
    does for the tool wrapped."""
    wrapper = _WRAPPERS.get(tool_cls)
    if wrapper is None:
        typed = next(
            sync for async_cls, sync in _TYPED if issubclass(tool_cls, async_cls)
        )
        wrapper = type(f"Sync{tool_cls.__name__}", (typed,), {"__module__": __name__})
        for base in tool_cls.__mro__:
            if isinstance(base, type) and issubclass(base, ToolSpec):
                base.register(wrapper)
        _WRAPPERS[tool_cls] = wrapper
    return wrapper


@overload
def make_sync_tool(
    async_tool: ElectricGripperTool, run: Callable[[Any], Any]
) -> SyncElectricGripperTool: ...
@overload
def make_sync_tool(
    async_tool: PneumaticGripperTool, run: Callable[[Any], Any]
) -> SyncPneumaticGripperTool: ...
@overload
def make_sync_tool(
    async_tool: GripperTool, run: Callable[[Any], Any]
) -> SyncGripperTool: ...
@overload
def make_sync_tool(async_tool: ToolSpec, run: Callable[[Any], Any]) -> SyncTool: ...
def make_sync_tool(async_tool: ToolSpec, run: Callable[[Any], Any]) -> SyncTool:
    """Wrap an async-bound tool for synchronous use.

    Every tool is wrapped, a metadata-only ``ToolSpec`` included: it still
    carries ``status``, ``action_l`` and ``action_r`` as coroutines, and a
    caller of the sync client must never get one of those back.
    """
    return _wrapper_for(type(async_tool))(async_tool, run)
