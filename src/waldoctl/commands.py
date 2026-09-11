"""The command table: what kind of thing each ``RobotClient`` method is.

A program is written once and runs against a live backend or a preview
client by swapping the client, so every wrapper around a client (the
stepping wrapper, the path preview, a backend's dry run) has to agree on
which calls queue on the controller, which mint a command index the
program may wait on, which cancel the queue, and which observe live state
a plan cannot predict. That agreement lives here, on the ABC, as data:
each method carries a ``@command`` marker and ``command_table()`` reads
them back, so a new method is classified where it is declared or the
conformance test in this package fails.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_MARKER = "__waldo_command__"


class CommandKind(Enum):
    """MOTION and QUEUED enter the controller's command queue and return its
    index; SYSTEM applies at once and returns the 1/0/negative code; CONTROL
    acts on the queue itself; QUERY reads state a plan knows; OBSERVATION
    reads live state only the running controller can answer; SYNC waits."""

    MOTION = "motion"
    QUEUED = "queued"
    SYSTEM = "system"
    CONTROL = "control"
    QUERY = "query"
    OBSERVATION = "observation"
    SYNC = "sync"


@dataclass(frozen=True)
class CommandSpec:
    name: str
    kind: CommandKind
    #: The call returns a queue index (``>= 0``) a program may ``wait_command``.
    mints_index: bool
    #: For MOTION: the path shape a preview renders (``joints``, ``cartesian``,
    #: ``smooth_arc``, ``smooth_spline``, ``jog``).
    move_type: str | None = None
    #: For CONTROL: discards what the queue and any blend hold were waiting on.
    cancels: bool = False


def command(
    kind: CommandKind,
    *,
    move_type: str | None = None,
    cancels: bool = False,
    mints_index: bool | None = None,
) -> Callable[[F], F]:
    """Classify a ``RobotClient`` method; see ``CommandKind``.

    Queued work returns its index unless the method says otherwise (a
    motion that returns a measurement, like ``estimate_payload``).
    """
    if (kind is CommandKind.MOTION) != (move_type is not None):
        raise ValueError("move_type is given for MOTION commands and only for them")
    if cancels and kind is not CommandKind.CONTROL:
        raise ValueError("only a CONTROL command cancels the queue")
    queued = kind in (CommandKind.MOTION, CommandKind.QUEUED)
    if mints_index is None:
        mints_index = queued
    elif mints_index and not queued:
        raise ValueError("only MOTION and QUEUED commands return a queue index")

    def mark(fn: F) -> F:
        setattr(
            fn,
            _MARKER,
            CommandSpec(
                name=getattr(fn, "__name__", ""),
                kind=kind,
                mints_index=mints_index,
                move_type=move_type,
                cancels=cancels,
            ),
        )
        return fn

    return mark


def _spec(cls: type, name: str) -> CommandSpec | None:
    """The marker on the nearest definition of *name* in the MRO that has
    one: an override without a marker keeps the ABC's classification."""
    for klass in cls.__mro__:
        member = vars(klass).get(name)
        spec = getattr(member, _MARKER, None)
        if isinstance(spec, CommandSpec):
            return spec
    return None


def command_table(cls: type | None = None) -> dict[str, CommandSpec]:
    """Every classified method of *cls* (default ``RobotClient``), by name."""
    if cls is None:
        from waldoctl.client import RobotClient

        cls = RobotClient
    table: dict[str, CommandSpec] = {}
    for name in dir(cls):
        if name.startswith("_"):
            continue
        spec = _spec(cls, name)
        if spec is not None:
            table[name] = spec
    return table


def unclassified(cls: type) -> list[str]:
    """Public functions of *cls* that carry no ``@command`` marker anywhere in
    the MRO."""
    return [
        name
        for name in dir(cls)
        if not name.startswith("_")
        and inspect.isfunction(inspect.getattr_static(cls, name))
        and _spec(cls, name) is None
    ]
