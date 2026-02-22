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

    Required methods: ``home()``, ``moveJ()``, ``moveL()``,
    ``get_angles()``, ``get_pose()``, ``flush()``.
    All other methods are optional (default raises ``NotImplementedError``).
    """

    # -- Required motion commands -------------------------------------------

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

    # -- Required queries ---------------------------------------------------

    @abstractmethod
    def get_angles(self) -> list[float]:
        """Get current simulated joint angles in degrees."""
        ...

    @abstractmethod
    def get_pose(self) -> list[float]:
        """Get current simulated pose as [x, y, z, rx, ry, rz]."""
        ...

    # -- Required lifecycle -------------------------------------------------

    @abstractmethod
    def flush(self) -> list[DryRunResult]:
        """Flush pending blend buffer. Call after script completion."""
        ...

    # -- Optional motion commands -------------------------------------------

    def moveC(
        self,
        via: list[float],
        end: list[float],
        **kwargs: Any,
    ) -> DryRunResult:
        """Simulate circular arc motion."""
        raise NotImplementedError

    def moveS(
        self,
        waypoints: list[list[float]],
        **kwargs: Any,
    ) -> DryRunResult:
        """Simulate cubic spline motion."""
        raise NotImplementedError

    def moveP(
        self,
        waypoints: list[list[float]],
        **kwargs: Any,
    ) -> DryRunResult:
        """Simulate process move."""
        raise NotImplementedError

    def servoJ(self, target: list[float], **kwargs: Any) -> DryRunResult:
        """Simulate streaming joint position."""
        raise NotImplementedError

    def servoL(self, pose: list[float], **kwargs: Any) -> DryRunResult:
        """Simulate streaming Cartesian position."""
        raise NotImplementedError

    def jogJ(self, speeds: list[float], **kwargs: Any) -> DryRunResult:
        """Simulate joint velocity jog."""
        raise NotImplementedError

    def jogL(self, velocities: list[float], **kwargs: Any) -> DryRunResult:
        """Simulate Cartesian velocity jog."""
        raise NotImplementedError

    # -- Optional configuration & control -----------------------------------

    def set_tool(self, tool_name: str, **kwargs: Any) -> DryRunResult | None:
        """Set active tool in simulation."""
        raise NotImplementedError

    def set_profile(self, profile: str, **kwargs: Any) -> DryRunResult | None:
        """Set motion profile in simulation."""
        raise NotImplementedError

    def checkpoint(self, label: str, **kwargs: Any) -> DryRunResult | None:
        """Insert checkpoint marker in simulation."""
        raise NotImplementedError

    def delay(self, seconds: float = 0.0) -> None:
        """No-op delay in simulation."""
        pass
