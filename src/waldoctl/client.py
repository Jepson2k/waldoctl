"""RobotClient ABC — async control operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from typing import Any

from waldoctl.status import PingResult, StatusBuffer, ToolResult
from waldoctl.tools import ToolSpec
from waldoctl.types import Axis, Frame


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
    def status_stream(self) -> AsyncIterator[StatusBuffer]:
        """Async iterator of real-time status snapshots (yields copies, safe to store)."""
        ...

    @abstractmethod
    def status_stream_shared(self) -> AsyncIterator[StatusBuffer]:
        """Async iterator of real-time status snapshots (shared buffer, zero-copy)."""
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
        frame: Frame = "WRF",
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

    # -- Advanced motion (optional) -----------------------------------------

    async def moveC(
        self,
        via: list[float],
        end: list[float],
        *,
        frame: Frame = "WRF",
        duration: float | None = None,
        speed: float | None = None,
        accel: float = 1.0,
        r: float = 0,
        wait: bool = False,
        **wait_kwargs: Any,
    ) -> int:
        """Circular arc move through *via* to *end*.

        Category: Motion

        Example:
            rbt.moveC(<via_pose>, <end_pose>, speed=0.5)
        """
        raise NotImplementedError

    async def moveS(
        self,
        waypoints: list[list[float]],
        *,
        frame: Frame = "WRF",
        duration: float | None = None,
        speed: float | None = None,
        accel: float = 1.0,
        wait: bool = False,
        **wait_kwargs: Any,
    ) -> int:
        """Cubic spline move through waypoints.

        Category: Motion

        Example:
            rbt.moveS(<waypoints>, speed=0.5)
        """
        raise NotImplementedError

    async def moveP(
        self,
        waypoints: list[list[float]],
        *,
        frame: Frame = "WRF",
        duration: float | None = None,
        speed: float | None = None,
        accel: float = 1.0,
        wait: bool = False,
        **wait_kwargs: Any,
    ) -> int:
        """Process move with auto-blending through waypoints.

        Category: Motion

        Example:
            rbt.moveP(<waypoints>, speed=0.5)
        """
        raise NotImplementedError

    # -- Servo commands (streaming position) --------------------------------

    @abstractmethod
    async def servoJ(
        self,
        target: list[float],
        *,
        pose: list[float] | None = None,
        speed: float = 1.0,
        accel: float = 1.0,
    ) -> int:
        """Streaming joint position target (fire-and-forget).

        *target*: joint angles in degrees (ignored if *pose* is set).
        If *pose* is given, dispatches to Cartesian target via IK.

        Category: Streaming

        Example:
            rbt.servoJ(<joint_angles_deg>)
        """
        ...

    @abstractmethod
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
        ...

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

        Category: Jog

        Example:
            rbt.jogJ(<joint_index>, speed=0.5, duration=1.0)
        """
        ...

    @abstractmethod
    async def jogL(
        self,
        frame: Frame,
        axis: Axis | None = None,
        speed: float = 0.0,
        duration: float = 0.1,
        *,
        axes: list[Axis] | None = None,
        speeds_list: list[float] | None = None,
        accel: float = 1.0,
    ) -> int:
        """Cartesian velocity jog. Single-axis or multi-axis.

        Single axis: ``jogL("WRF", "X", 0.5, 1.0)``
        Multi axis:  ``jogL("WRF", axes=["X", "Y"], speeds_list=[0.5, -0.3])``

        Category: Jog

        Example:
            rbt.jogL("WRF", "X", speed=0.5, duration=1.0)
        """
        ...

    # -- Synchronization ----------------------------------------------------

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

    @abstractmethod
    async def wait_command_complete(
        self,
        command_index: int,
        timeout: float = 10.0,
    ) -> bool:
        """Block until a specific command index has completed.

        Category: Synchronization

        Example:
            rbt.wait_command_complete(<index>)
        """
        ...

    async def wait_for_status(
        self,
        predicate: Callable[[StatusBuffer], bool],
        timeout: float = 5.0,
    ) -> bool:
        """Block until *predicate* returns True for a status snapshot."""
        raise NotImplementedError

    async def wait_for_checkpoint(
        self,
        label: str,
        timeout: float = 30.0,
    ) -> bool:
        """Block until a checkpoint with *label* is reached."""
        raise NotImplementedError

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

    # -- Queries (required) -------------------------------------------------

    @abstractmethod
    async def get_angles(self) -> list[float] | None:
        """Get current joint angles in degrees.

        Category: Query

        Example:
            angles = rbt.get_angles()
        """
        ...

    @abstractmethod
    async def get_pose(self, frame: Frame = "WRF") -> list[float] | None:
        """Get current pose as flattened 4x4 matrix.

        Category: Query

        Example:
            pose = rbt.get_pose()
        """
        ...

    @abstractmethod
    async def get_pose_rpy(self) -> list[float] | None:
        """Get current pose as [x, y, z, rx, ry, rz].

        Category: Query

        Example:
            pose = rbt.get_pose_rpy()
        """
        ...

    # -- Queries (optional) -------------------------------------------------

    async def get_speeds(self) -> list[float] | None:
        """Get current joint speeds.

        Category: Query

        Example:
            speeds = rbt.get_speeds()
        """
        raise NotImplementedError

    async def get_io(self) -> list[int] | None:
        """Get digital I/O state.

        Category: Query

        Example:
            io = rbt.get_io()
        """
        raise NotImplementedError

    async def get_status(self) -> object | None:
        """Get aggregate status snapshot.

        Category: Query

        Example:
            status = rbt.get_status()
        """
        raise NotImplementedError

    async def get_queue(self) -> list[str] | None:
        """Get queued command list.

        Category: Query

        Example:
            queue = rbt.get_queue()
        """
        raise NotImplementedError

    async def get_tool(self) -> ToolResult | None:
        """Get current tool and available tools.

        Category: Query

        Example:
            tool = rbt.get_tool()
        """
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

    async def set_tool(self, tool_name: str) -> int:
        """Set the active end-effector tool on the controller.

        Category: Configuration

        Example:
            rbt.set_tool("PNEUMATIC")
        """
        raise NotImplementedError

    # -- I/O & Tools --------------------------------------------------------

    @property
    def tool(self) -> ToolSpec:
        """The active bound tool.

        Raises ``RuntimeError`` if no tool has been set.
        """
        raise NotImplementedError

    async def set_io(self, index: int, value: int) -> int:
        """Set digital output by logical index (0 = first output pin).

        Category: I/O

        Example:
            rbt.set_io(0, 1)   # Set first output HIGH
        """
        raise NotImplementedError

    async def tool_action(
        self,
        tool_key: str,
        action: str,
        params: list[Any] | None = None,
        *,
        wait: bool = False,
        timeout: float = 10.0,
    ) -> int:
        """Invoke a tool-specific action by key.

        *tool_key*: identifier of the attached tool (e.g. ``"ELECTRIC"``).
        *action*: action name understood by the tool (e.g. ``"calibrate"``, ``"move"``).
        *params*: optional positional parameters for the action.

        Category: I/O

        Example:
            rbt.tool_action("ELECTRIC", "calibrate")
        """
        raise NotImplementedError

    # -- Queue control ------------------------------------------------------

    async def reset(self) -> int:
        """Reset controller state.

        Category: Control

        Example:
            rbt.reset()
        """
        raise NotImplementedError

    async def checkpoint(self, label: str) -> int:
        """Insert a checkpoint marker in the command queue.

        Category: Synchronization

        Example:
            rbt.checkpoint("pick_done")
        """
        raise NotImplementedError

    async def delay(self, seconds: float) -> int:
        """Insert a non-blocking delay in the command queue.

        Category: Synchronization

        Example:
            rbt.delay(1.0)
        """
        raise NotImplementedError
