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

    Required methods: ``home()``, ``moveJ()``, ``moveL()``,
    ``get_angles()``, ``get_pose()``, ``flush()``.
    """

    # -- Required motion commands -------------------------------------------

    def home(self, **kwargs: Any) -> DryRunResult | None: ...

    def moveJ(
        self,
        target: list[float],
        *,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        **kwargs: Any,
    ) -> DryRunResult | None: ...

    def moveL(
        self,
        pose: list[float],
        *,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        **kwargs: Any,
    ) -> DryRunResult | None: ...

    # -- Required queries ---------------------------------------------------

    def get_angles(self) -> list[float]: ...

    def get_pose(self) -> list[float]: ...

    # -- Required tool access -----------------------------------------------

    @property
    def tool(self) -> Any: ...

    # -- Required lifecycle -------------------------------------------------

    def flush(self) -> list[DryRunResult]: ...
