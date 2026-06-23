"""DryRunClient Protocol — offline motion simulation for path preview."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from waldoctl.results import DryRunResult


@runtime_checkable
class DryRunClient(Protocol):
    """Offline motion client for path preview / dry-run simulation.

    Concrete implementations run the real command pipeline against a
    simulated controller state without hardware.  Each motion method
    returns a ``DryRunResult`` containing the TCP trajectory and final
    joint state.

    Required methods: ``home()``, ``move_j()``, ``move_l()``,
    ``angles()``, ``pose()``, ``flush()``.
    """

    def home(self, **kwargs: Any) -> DryRunResult | None: ...

    def move_j(
        self,
        angles: list[float] | None = None,
        *,
        pose: list[float] | None = None,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        **kwargs: Any,
    ) -> DryRunResult | None: ...

    def move_l(
        self,
        pose: list[float],
        *,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        **kwargs: Any,
    ) -> DryRunResult | None: ...

    def angles(self) -> list[float]: ...

    def pose(self) -> list[float]: ...

    @property
    def tool(self) -> Any: ...

    def flush(self) -> list[DryRunResult]: ...
