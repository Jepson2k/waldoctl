"""Synchronous tool wrappers — mirrors the sync/async client split.

A sync tool is the async tool behind a ``run`` function (typically the
sync client's loop runner): every coroutine method comes back as a plain
call, everything else is the async tool's own attribute.

The wrapper does not inherit from the tool it wraps. Inheriting looked
like the way to keep ``isinstance`` working, but it meant every attribute
the async base defines resolved on the wrapper FIRST — so a coroutine the
wrapper had not hand-listed came back un-awaited, and a property a
backend overrides was answered by the base. Both are the same defect: a
list of names to keep in step with a class somewhere else. Composition
has no list. ``isinstance`` is kept by registering the wrapper with the
ABCs of the tool it wraps.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, cast

from waldoctl.tools import ToolSpec

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


_WRAPPERS: dict[type, type[SyncTool]] = {}


def _wrapper_for(tool_cls: type) -> type[SyncTool]:
    """The ``SyncTool`` subclass standing in for ``tool_cls``.

    One per async class, registered with every ``ToolSpec`` ABC in that
    class's MRO — the concrete class included — so ``isinstance(sync,
    ElectricGripperTool)`` is true exactly when it is for the tool
    wrapped, and false for a pneumatic gripper's wrapper.
    """
    wrapper = _WRAPPERS.get(tool_cls)
    if wrapper is None:
        wrapper = type(
            f"Sync{tool_cls.__name__}", (SyncTool,), {"__module__": __name__}
        )
        for base in tool_cls.__mro__:
            if isinstance(base, type) and issubclass(base, ToolSpec):
                base.register(wrapper)
        _WRAPPERS[tool_cls] = wrapper
    return wrapper


def make_sync_tool(async_tool: ToolSpec, run: Callable[[Any], Any]) -> ToolSpec:
    """Wrap an async-bound tool for synchronous use.

    Every tool is wrapped, a metadata-only ``ToolSpec`` included: it still
    carries ``status``, ``action_l`` and ``action_r`` as coroutines, and a
    caller of the sync client must never get one of those back.
    """
    return cast(ToolSpec, _wrapper_for(type(async_tool))(async_tool, run))
