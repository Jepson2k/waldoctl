"""RobotClient ABC — async control operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from waldoctl.status import PingResult, StatusBuffer, ToolResult


class RobotClient(ABC):
    """Generic async robot control interface.

    Backends inherit from this ABC and implement the required abstract
    methods.  Optional methods have concrete defaults that raise
    ``NotImplementedError``.

    **Command palette integration:** Methods that should appear in the editor's
    command palette must include ``Category:`` and ``Example:`` sections in
    their docstrings.  The editor parses these at startup to build the palette.

    - ``Category: <name>`` — groups the command in the palette UI.
    - ``Example:`` — the first indented line becomes the insertion snippet.
    """

    # -- Connection & lifecycle ---------------------------------------------

    @abstractmethod
    async def close(self) -> None:
        """Release resources and disconnect."""
        ...

    @abstractmethod
    async def ping(self) -> PingResult | None:
        """Check connectivity.  Returns None if unreachable.

        Category: Query

        Example:
            rbt.ping()
        """
        ...

    @abstractmethod
    async def wait_ready(self, timeout: float = 5.0, interval: float = 0.05) -> bool:
        """Block until the robot backend is reachable or *timeout* expires."""
        ...

    # -- Status streaming ---------------------------------------------------

    @abstractmethod
    def status_stream_shared(self) -> AsyncIterator[StatusBuffer]:
        """Async iterator of real-time status snapshots (shared across consumers)."""
        ...

    # -- Motion commands (trajectory-planned) ---------------------------------

    @abstractmethod
    async def moveJ(
        self,
        target: list[float],
        *,
        pose: list[float] | None = None,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        r: float = 0,
        rel: bool = False,
        wait: bool = False,
        **wait_kwargs: Any,
    ) -> int:
        """Joint-space move. *target*: joint angles in degrees.

        If *pose* is given, performs joint-interpolated move to Cartesian target.
        Returns the command index (>= 0) on success, -1 on failure.

        Category: Motion

        Example:
            rbt.moveJ(<joint_angles_deg>, speed=0.5)
        """
        ...

    @abstractmethod
    async def moveL(
        self,
        pose: list[float],
        *,
        frame: str = "WRF",
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        r: float = 0,
        rel: bool = False,
        wait: bool = False,
        **wait_kwargs: Any,
    ) -> int:
        """Linear Cartesian move to [x, y, z, rx, ry, rz].

        Returns the command index (>= 0) on success, -1 on failure.

        Category: Motion

        Example:
            rbt.moveL(<tcp_pose_mm_deg>, speed=0.5)
        """
        ...

    @abstractmethod
    async def home(self, wait: bool = False, **wait_kwargs: Any) -> int:
        """Move to the robot's home position.

        Returns the command index (>= 0) on success, -1 on failure.

        Category: Motion

        Example:
            rbt.home()
        """
        ...

    @abstractmethod
    async def wait_motion_complete(
        self,
        timeout: float = 10.0,
        **kwargs: Any,
    ) -> bool:
        """Block until the robot has stopped moving or *timeout* expires.

        Category: Synchronization

        Example:
            rbt.wait_motion_complete()
        """
        ...

    # -- Servo commands (streaming position, fire-and-forget) ---------------

    async def servoJ(
        self,
        target: list[float],
        *,
        pose: list[float] | None = None,
        speed: float = 1.0,
        accel: float = 1.0,
    ) -> int:
        """Streaming joint position target (fire-and-forget).

        *target*: 6 joint angles in degrees (ignored if *pose* is set).
        If *pose* is given, dispatches to SERVOJ_POSE (Cartesian target via IK).

        Category: Streaming

        Example:
            rbt.servoJ(<joint_angles_deg>)
        """
        raise NotImplementedError

    async def servoL(
        self,
        pose: list[float],
        *,
        speed: float = 1.0,
        accel: float = 1.0,
    ) -> int:
        """Streaming linear Cartesian position target (fire-and-forget).

        *pose*: [x, y, z, rx, ry, rz] in mm and degrees.

        Category: Streaming

        Example:
            rbt.servoL(<tcp_pose_mm_deg>)
        """
        raise NotImplementedError

    # -- Jog commands (streaming velocity) ----------------------------------

    @abstractmethod
    async def jogJ(
        self,
        joint: int,
        speed: float = 0.0,
        duration: float = 0.1,
        *,
        joints: list[int] | None = None,
        speeds: list[float] | None = None,
        accel: float = 1.0,
    ) -> int:
        """Joint velocity jog. Single-joint or multi-joint.

        Single joint: ``jogJ(0, 0.5, 1.0)``
        Multi joint:  ``jogJ(joints=[0, 1], speeds=[0.5, -0.3], duration=1.0)``

        *joint*: 0-based joint number (single-joint mode).
        *speed*: signed, ``-1.0`` to ``1.0`` (single-joint mode).
        *duration*: seconds per pulse.
        *joints*: list of joint indices (multi-joint mode).
        *speeds*: list of signed speed fractions (multi-joint mode).
        *accel*: acceleration fraction 0-1.

        Category: Jog

        Example:
            rbt.jogJ(<joint_index>, speed=0.5, duration=1.0)
        """
        ...

    @abstractmethod
    async def jogL(
        self,
        frame: str,
        axis: str | None = None,
        speed: float = 0.0,
        duration: float = 0.1,
        *,
        axes: list[str] | None = None,
        speeds_list: list[float] | None = None,
        accel: float = 1.0,
    ) -> int:
        """Cartesian velocity jog. Single-axis or multi-axis.

        Single axis: ``jogL("WRF", "X", 0.5, 1.0)``
        Multi axis:  ``jogL("WRF", axes=["X", "Y"], speeds_list=[0.5, -0.3])``

        *frame*: reference frame (``"WRF"`` or ``"TRF"``).
        *axis*: axis name for single-axis jog.
        *speed*: signed, ``-1.0`` to ``1.0`` (single-axis mode).
        *duration*: seconds per pulse.
        *axes*: list of axis names (multi-axis mode).
        *speeds_list*: list of signed speed fractions (multi-axis mode).
        *accel*: acceleration fraction 0-1.

        Category: Jog

        Example:
            rbt.jogL("WRF", "X", speed=0.5, duration=1.0)
        """
        ...

    # -- Safety & mode ------------------------------------------------------

    @abstractmethod
    async def resume(self) -> int:
        """Re-enable the robot after an e-stop or disable.

        Category: Control

        Example:
            rbt.resume()
        """
        ...

    @abstractmethod
    async def halt(self) -> int:
        """Immediate stop — halt all motion and disable.

        Category: Control

        Example:
            rbt.halt()
        """
        ...

    async def simulator_on(self) -> int:
        """Enable simulator mode.

        Category: Control

        Example:
            rbt.simulator_on()
        """
        raise NotImplementedError

    async def simulator_off(self) -> int:
        """Disable simulator mode.

        Category: Control

        Example:
            rbt.simulator_off()
        """
        raise NotImplementedError

    async def set_freedrive(self, enabled: bool) -> int:
        """Enable or disable freedrive / teach mode."""
        raise NotImplementedError

    # -- Configuration ------------------------------------------------------

    async def set_serial_port(self, port_str: str) -> int:
        """Set the serial port for hardware communication.

        Category: Configuration

        Example:
            rbt.set_serial_port("/dev/ttyUSB0")
        """
        raise NotImplementedError

    async def set_profile(self, profile: str) -> int:
        """Set the motion profile (e.g. ``"TOPPRA"``).

        Category: Configuration

        Example:
            rbt.set_profile("TOPPRA")
        """
        raise NotImplementedError

    async def get_tool(self) -> ToolResult | None:
        """Get current tool and available tools.

        Category: Query

        Example:
            tool = rbt.get_tool()
        """
        raise NotImplementedError

    async def set_tool(self, tool_name: str) -> int:
        """Set the active end-effector tool on the controller.

        Category: Configuration

        Example:
            rbt.set_tool("PNEUMATIC")
        """
        raise NotImplementedError

    # -- Gripper / I/O ------------------------------------------------------

    async def control_pneumatic_gripper(
        self, action: str, port: int, wait: bool = False, **wait_kwargs: Any
    ) -> int:
        """Control pneumatic gripper.  *action*: ``"open"`` or ``"close"``.

        Category: Gripper

        Example:
            rbt.control_pneumatic_gripper("open", port=1)
        """
        raise NotImplementedError

    async def control_electric_gripper(
        self,
        action: str,
        position: float = 0.0,
        speed: float = 0.5,
        current: int = 500,
        wait: bool = False,
        **wait_kwargs: Any,
    ) -> int:
        """Control electric gripper.  *action*: ``"calibrate"``, ``"move"``, etc.

        Category: Gripper

        Example:
            rbt.control_electric_gripper("move", position=0.5)
        """
        raise NotImplementedError
