"""DryRunClient ABC — offline motion simulation for path preview."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from waldoctl.results import DryRunResult


class DryRunClient(ABC):
    """Offline motion client for path preview / dry-run simulation.

    Concrete implementations run the real command pipeline against a
    simulated controller state without hardware.  Each motion method
    returns a ``DryRunResult`` containing the TCP trajectory and final
    joint state.
    """

    @abstractmethod
    def home(self, **kwargs: Any) -> DryRunResult:
        """Simulate homing motion."""
        ...

    @abstractmethod
    def moveJ(
        self,
        target: list[float],
        *,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        **kwargs: Any,
    ) -> DryRunResult:
        """Simulate joint-space motion."""
        ...

    @abstractmethod
    def moveL(
        self,
        pose: list[float],
        *,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        **kwargs: Any,
    ) -> DryRunResult:
        """Simulate Cartesian linear motion."""
        ...
