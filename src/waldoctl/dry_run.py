"""DryRunClient Protocol — the offline client a program runs against for a preview."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from waldoctl.ticks import TickIndex

if TYPE_CHECKING:
    from waldoctl.robot import Robot


@runtime_checkable
class DryRunClient(Protocol):
    """Offline client for path preview.

    A concrete implementation runs the real command pipeline against a
    simulated controller state without hardware, and answers the program it
    is given with two tick-indexed records: ``plan()`` is the *commanded*
    one, the planner's answer, fast enough to run behind a keystroke;
    ``simulate()`` is the *predicted* one, the same commands through the
    backend's control loop and plant. A backend with no plant returns the
    plan from ``simulate()`` too — predicted equals commanded.

    Command methods answer as the live client does. MOTION and QUEUED calls
    return the program index: the ``TickBlock.command`` of the block they
    produce, which is ``program_length - 1`` on return. Motions that mint no
    index (jogs, servo) return the ``1``/``0``/negative code. A refusal
    surfaces the way the live client surfaces it, and always leaves a
    zero-row block carrying the error, so a preview shows every mistake in
    the file rather than stopping at the first.
    """

    @property
    def robot(self) -> Robot | None:
        """The backend this preview stands in for; a skill checks its
        requirements against it. Read-only here: a backend's client accepts
        only its own ``Robot``, which the host sets on the concrete client
        it constructed."""
        ...

    @property
    def tool(self) -> Any: ...

    @property
    def program_length(self) -> int:
        """Commands recorded so far — ``len(plan().blocks)``."""
        ...

    def home(self, **kwargs: Any) -> int: ...

    def move_j(
        self,
        angles: list[float] | None = None,
        *,
        pose: list[float] | None = None,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        **kwargs: Any,
    ) -> int: ...

    def move_l(
        self,
        pose: list[float],
        *,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        **kwargs: Any,
    ) -> int: ...

    def delay(self, seconds: float) -> int:
        """Hold the pose for *seconds*: rows on the commanded record."""
        ...

    def checkpoint(self, label: str) -> int: ...

    def wait_command(self, command_index: int, timeout: float = 10.0) -> bool:
        """Whether the block for *command_index* planned without error."""
        ...

    def angles(self) -> list[float]: ...

    def pose(self) -> list[float]: ...

    def flush(self) -> None:
        """Close any pending blend group."""
        ...

    def plan(self, max_seconds: float | None = None) -> TickIndex:
        """The commanded record for everything submitted so far.

        Closes any pending blend group first. ``max_seconds`` truncates the
        record to ``ceil(max_seconds / row_dt_s)`` rows and reports
        ``stop="budget_exhausted"``.
        """
        ...

    def simulate(self, max_seconds: float | None = None) -> TickIndex:
        """The predicted record for everything submitted so far.

        ``max_seconds`` bounds simulated time. A planner-only backend returns
        exactly what ``plan()`` returns.
        """
        ...
