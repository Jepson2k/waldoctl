"""Composable Python skills and their client execution contract.

The supplied client owns the connection, loop and command policy. This module
never connects to a robot or imports Commander state. Entry points expose
decorated functions through ``waldoctl.skills``; ordinary imports need no registry.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import update_wrapper
from importlib.metadata import entry_points
from typing import (
    Any,
    Concatenate,
    Generic,
    Literal,
    ParamSpec,
    Protocol,
    TypeVar,
    cast,
)
from uuid import uuid4

from waldoctl.client import RobotClient
from waldoctl.record_values import snapshot_arguments, snapshot_value

P = ParamSpec("P")
R = TypeVar("R")
ClientT = TypeVar("ClientT", bound=RobotClient)
ClientCo = TypeVar("ClientCo", bound=RobotClient, covariant=True)
logger = logging.getLogger(__name__)
SKILL_API_VERSION = 1
SkillPhase = Literal["started", "progress", "completed", "failed", "cancelled"]


class SyncSkillClient(Protocol[ClientCo]):
    """A sync facade runs the invocation on its own loop and async view.

    Wrappers MUST implement this hook themselves, supplying an async view
    with the same interception/policy as the outer facade. Delegating a bound
    hook through ``__getattr__`` would silently bypass that policy.
    """

    def run_skill(self, invoke: Callable[[ClientCo], Coroutine[Any, Any, R]]) -> R: ...


@dataclass(frozen=True)
class SkillSpec:
    id: str
    version: str
    requires: frozenset[str] = frozenset()
    api_version: int = SKILL_API_VERSION

    def __post_init__(self) -> None:
        if type(self.api_version) is not int or self.api_version < 1:
            raise ValueError("Skill API version must be a positive integer")
        if not re.fullmatch(r"[a-z][a-z0-9_.-]*", self.id):
            raise ValueError(
                "Skill id must be a stable lowercase, namespaced identifier"
            )
        if not re.fullmatch(r"\d+\.\d+\.\d+", self.version):
            raise ValueError("Skill version must have major.minor.patch form")
        if isinstance(self.requires, str):
            # `requires="motion"` would become a frozenset of its letters, and
            # every letter is a valid identifier, so the skill would register
            # and then demand capabilities named m, o, t, i and n.
            raise ValueError(
                "Capabilities must be a collection of identifiers, not one string"
            )
        object.__setattr__(self, "requires", frozenset(self.requires))
        if any(not re.fullmatch(r"[a-z][a-z0-9_.-]*", key) for key in self.requires):
            raise ValueError("Capabilities must be nonempty lowercase identifiers")


@dataclass(frozen=True)
class SkillEvent:
    invocation_id: str
    parent_id: str | None
    skill: SkillSpec
    phase: SkillPhase
    message: str = ""
    fraction: float | None = None
    stop_confirmed: bool | None = None
    values_captured: bool = False
    arguments: Any = None
    result: Any = None


class SkillError(RuntimeError):
    """The skill could not execute; expected domain outcomes remain return values."""


class MissingCapability(SkillError):
    """The supplied client cannot provide a required operation."""


class IncompatibleSkill(SkillError):
    """The skill requires a different runtime API."""


def _check_api(spec: SkillSpec) -> None:
    if spec.api_version != SKILL_API_VERSION:
        raise IncompatibleSkill(
            f"{spec.id} requires skill API {spec.api_version}; this runtime provides {SKILL_API_VERSION}. Install a compatible plugin/runtime version."
        )


class UnresolvedPreview(SkillError):
    """A preview needs an explicit observation fixture to choose this branch."""


@dataclass
class _Execution:
    client: RobotClient
    cancelled: bool = False
    closed: bool = False
    stop_confirmed: bool | None = None
    stop_task: asyncio.Task[bool] | None = None

    def check(self) -> None:
        task = asyncio.current_task()
        if self.cancelled or (task is not None and task.cancelling()):
            self.cancelled = True
            raise asyncio.CancelledError
        if self.closed:
            raise SkillError("The skill invocation has already finished")

    async def stop(self) -> None:
        self.cancelled = True
        if self.stop_task is None:

            async def request_stop() -> bool:
                try:
                    result = await asyncio.wait_for(self.client.stop(), timeout=2.0)
                    return result > 0
                except Exception:
                    logger.exception("Skill cancellation stop could not be confirmed")
                    return False

            self.stop_task = asyncio.create_task(request_stop())
        # Repeated cancellation must not abandon the stop request. The request
        # itself has a deadline and cannot keep this task alive indefinitely.
        while not self.stop_task.done():
            try:
                await asyncio.shield(self.stop_task)
            except asyncio.CancelledError:
                continue
        self.stop_confirmed = self.stop_task.result()


@dataclass
class _Invocation:
    spec: SkillSpec
    execution: _Execution
    parent_id: str | None
    id: str = field(default_factory=lambda: uuid4().hex)

    def emit(
        self,
        phase: SkillPhase,
        *,
        arguments: Any = None,
        result: Any = None,
        **kwargs: Any,
    ) -> None:
        for observer, capture in _observers.get():
            try:
                event = SkillEvent(
                    self.id,
                    self.parent_id,
                    self.spec,
                    phase,
                    values_captured=capture,
                    arguments=snapshot_value(arguments) if capture else None,
                    result=snapshot_value(result) if capture else None,
                    **kwargs,
                )
                observer(event)
            except Exception:
                # A logging/UI extension must not interrupt a motion sequence.
                logger.exception("Skill event observer failed")


_active: ContextVar[_Invocation | None] = ContextVar("waldoctl_skill", default=None)
_observers: ContextVar[tuple[tuple[Callable[[SkillEvent], None], bool], ...]] = (
    ContextVar("waldoctl_skill_observers", default=())
)


@contextmanager
def observe_skills(
    observer: Callable[[SkillEvent], None], *, capture_values: bool = False
) -> Iterator[None]:
    """Observe invocations in this execution context, including nested skills.

    Callbacks run on the client's execution thread. UI consumers must marshal
    events to their own loop. Arguments/results require explicit opt-in and are
    bounded, detached snapshots, excluding the supplied client. They may contain
    personal data. Observer failures are logged and isolated.
    """
    token = _observers.set((*_observers.get(), (observer, capture_values)))
    try:
        yield
    finally:
        _observers.reset(token)


def report_progress(message: str, *, fraction: float | None = None) -> None:
    """Report progress for the current invocation; no global GUI is required."""
    invocation = _active.get()
    if invocation is None:
        raise SkillError("Progress can only be reported while executing a skill")
    invocation.execution.check()
    if fraction is not None and not 0 <= fraction <= 1:
        raise ValueError("Progress fraction must be finite and between 0 and 1")
    invocation.emit("progress", message=message, fraction=fraction)


def current_skill_invocation() -> str | None:
    """Correlation id for command observers inside an executing skill."""
    invocation = _active.get()
    return invocation.id if invocation is not None else None


class _Guard:
    """Keep cancellation sticky across nested skills and supplied tool calls."""

    def __init__(self, target: Any, execution: _Execution) -> None:
        self._target = target
        self._execution = execution

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        self._execution.check()
        attr = getattr(self._target, name)
        if name == "tool":
            return _Guard(attr, self._execution)
        if not callable(attr) or not inspect.iscoroutinefunction(attr):
            return attr

        async def call(*args: Any, **kwargs: Any) -> Any:
            # Yield even when a preview or an in-process backend completes an
            # operation synchronously, so cancellation has a boundary to land.
            await asyncio.sleep(0)
            self._execution.check()
            result = await attr(*args, **kwargs)
            self._execution.check()
            return result

        return call


class Skill(Generic[ClientT, P, R]):
    """One typed async implementation with sync and explicit async entry points."""

    def __init__(
        self,
        function: Callable[Concatenate[ClientT, P], Coroutine[Any, Any, R]],
        spec: SkillSpec,
    ) -> None:
        if not inspect.iscoroutinefunction(function):
            raise TypeError("A skill must be defined with async def")
        if not inspect.signature(function).parameters:
            raise TypeError(
                "A skill must accept an explicit client as its first argument"
            )
        self.function = function
        self.spec = spec
        update_wrapper(self, function)

    def __call__(
        self, client: SyncSkillClient[ClientT], /, *args: P.args, **kwargs: P.kwargs
    ) -> R:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return client.run_skill(
                lambda async_client: self.async_call(async_client, *args, **kwargs)
            )
        raise RuntimeError(
            "Use await skill.async_call(async_client, ...) inside an event loop"
        )

    async def async_call(
        self, client: ClientT, /, *args: P.args, **kwargs: P.kwargs
    ) -> R:
        parent = _active.get()
        # Only composition through the SAME supplied guarded client shares
        # cancellation. Another explicitly supplied robot owns a separate stop.
        execution = (
            client._execution if isinstance(client, _Guard) else _Execution(client)
        )
        root = not isinstance(client, _Guard)
        invocation = _Invocation(self.spec, execution, parent.id if parent else None)
        token = _active.set(invocation)
        capture = any(enabled for _, enabled in _observers.get())
        arguments = (
            snapshot_arguments(self.function, (client, *args), kwargs, omit_first=True)
            if capture
            else None
        )
        invocation.emit("started", arguments=arguments)
        try:
            execution.check()
            _check_api(self.spec)
            missing = self.spec.requires - client.skill_capabilities
            if missing:
                raise MissingCapability(
                    f"{self.spec.id} requires: {', '.join(sorted(missing))}"
                )
            guarded = cast(ClientT, _Guard(client, execution)) if root else client
            result = await self.function(guarded, *args, **kwargs)
            execution.check()
            invocation.emit("completed", result=result if capture else None)
            return result
        except asyncio.CancelledError:
            # Only the root invocation owns the arm: a CancelledError leaving a
            # nested skill may be an enclosing asyncio.timeout() in the parent,
            # which converts it to TimeoutError and carries on.
            if root:
                await execution.stop()
            invocation.emit("cancelled", stop_confirmed=execution.stop_confirmed)
            raise
        except Exception as error:
            invocation.emit("failed", message=str(error))
            raise
        finally:
            if root:
                execution.closed = True
            _active.reset(token)


def skill(
    *,
    id: str,
    version: str,
    requires: frozenset[str] = frozenset(),
    api_version: int = SKILL_API_VERSION,
) -> Callable[
    [Callable[Concatenate[ClientT, P], Coroutine[Any, Any, R]]], Skill[ClientT, P, R]
]:
    """Decorate an async function; metadata never changes its Python arguments."""
    spec = SkillSpec(id, version, requires, api_version)

    def decorate(
        function: Callable[Concatenate[ClientT, P], Coroutine[Any, Any, R]],
    ) -> Skill[ClientT, P, R]:
        return Skill(function, spec)

    return decorate


def discover_skills(
    *, diagnostics: list[str] | None = None
) -> dict[str, Skill[Any, ..., Any]]:
    """Load installed skills, diagnosing broken plugins and rejecting conflicts.

    All providers of a duplicated skill id are excluded, independent of entry
    point ordering. A broken provider does not prevent unrelated skills loading.
    """
    found: dict[str, Skill[Any, ..., Any]] = {}
    conflicts: set[str] = set()
    for ep in sorted(
        entry_points(group="waldoctl.skills"), key=lambda ep: (ep.name, ep.value)
    ):
        try:
            candidate = ep.load()
            if not isinstance(candidate, Skill):
                raise TypeError("entry point must reference an @skill callable")
            _check_api(candidate.spec)
            key = candidate.spec.id
            if key in found or key in conflicts:
                found.pop(key, None)
                conflicts.add(key)
                logger.warning("Conflicting skill id %r; all providers excluded", key)
                if diagnostics is not None:
                    diagnostics.append(
                        f"Conflicting skill id {key!r}; all providers excluded. Give each implementation a unique id."
                    )
                continue
            found[key] = candidate
        except Exception as error:
            logger.exception("Cannot load skill plugin %s (%s)", ep.name, ep.value)
            if diagnostics is not None:
                diagnostics.append(f"Cannot load {ep.name} ({ep.value}): {error}")
    return found
