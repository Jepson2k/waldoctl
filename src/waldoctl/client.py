"""RobotClient ABC — async control operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from typing import Any

from waldoctl.shapes import Shape, ShapeWorld
from waldoctl.status import (
    ActivityResult,
    LoopStatsResult,
    Inertia6,
    PayloadEstimate,
    PayloadResult,
    PingResult,
    StatusBuffer,
    ToolResult,
)
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

    **Command return codes:** Command methods declared ``-> int`` follow one
    convention, which backends MUST honor:

    - Queued motion commands (Category: Motion) return the command's queue
      index (``>= 0``) once the backend acknowledges it; ``< 0`` when the
      command could not be confirmed or was rejected.
    - Every other command returns ``1`` when the backend confirmed it applied
      the command, ``0`` when unconfirmed (unreachable, or no reply in time —
      the command may or may not have been applied), and ``< 0`` on rejection.
      A backend may raise instead of returning a negative code on active
      rejection; callers must treat both as failure.

    A backend that cannot confirm application must never report success.
    Success is ``>= 0`` for queued motion, ``> 0`` for everything else.
    """

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

    @abstractmethod
    def stream_status(self) -> AsyncIterator[StatusBuffer]:
        """Async iterator of real-time status snapshots (yields copies, safe to store)."""
        ...

    @abstractmethod
    def stream_status_shared(self) -> AsyncIterator[StatusBuffer]:
        """Async iterator of real-time status snapshots (shared buffer, zero-copy)."""
        ...

    @abstractmethod
    async def move_j(
        self,
        angles: list[float] | None = None,
        *,
        pose: list[float] | None = None,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        r: float = 0.0,
        rel: bool = False,
        wait: bool = False,
        timeout: float = 10.0,
        **wait_kwargs: Any,
    ) -> int:
        """Joint-space move. *angles*: joint angles in degrees.

        If *pose* is given, performs joint-interpolated move to Cartesian target.
        Returns the command index (>= 0) on success, -1 on failure.

        Category: Motion

        Example:
            rbt.move_j(<joint_angles_deg>, speed=0.5)
        """
        ...

    @abstractmethod
    async def move_l(
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
            rbt.move_l(<tcp_pose_mm_deg>, speed=0.5)
        """
        ...

    @abstractmethod
    async def home(
        self, wait: bool = False, calibrate: bool = False, **wait_kwargs: Any
    ) -> int:
        """Move to the robot's home position.

        An uncalibrated robot (first home after power-on) always runs the
        backend's calibration sequence — searching for its end stops to
        establish joint references — and ends at the home position. Once
        calibrated, ``home()`` is a planned move to the home position;
        ``calibrate=True`` re-runs the calibration sequence instead.

        Returns the command index (>= 0) on success, -1 on failure.

        Category: Motion

        Example:
            rbt.home()
        """
        ...

    async def move_c(
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
            rbt.move_c(<via_pose>, <end_pose>, speed=0.5)
        """
        raise NotImplementedError

    async def move_s(
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
            rbt.move_s(<waypoints>, speed=0.5)
        """
        raise NotImplementedError

    async def move_p(
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
            rbt.move_p(<waypoints>, speed=0.5)
        """
        raise NotImplementedError

    @abstractmethod
    async def servo_j(
        self,
        angles: list[float],
        *,
        pose: list[float] | None = None,
        speed: float = 1.0,
        accel: float = 1.0,
    ) -> int:
        """Streaming joint position target (fire-and-forget).

        *angles*: joint angles in degrees (ignored if *pose* is set).
        If *pose* is given, dispatches to Cartesian target via IK.

        Category: Streaming

        Example:
            rbt.servo_j(<joint_angles_deg>)
        """
        ...

    @abstractmethod
    async def servo_l(
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
            rbt.servo_l(<tcp_pose_mm_deg>)
        """
        ...

    @abstractmethod
    async def jog_j(
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

        Single joint: ``jog_j(0, 0.5, 1.0)``
        Multi joint:  ``jog_j(joints=[0, 1], speeds=[0.5, -0.3], duration=1.0)``

        Category: Jog

        Example:
            rbt.jog_j(<joint_index>, speed=0.5, duration=1.0)
        """
        ...

    @abstractmethod
    async def jog_l(
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

        Single axis: ``jog_l("WRF", "X", 0.5, 1.0)``
        Multi axis:  ``jog_l("WRF", axes=["X", "Y"], speeds_list=[0.5, -0.3])``

        Category: Jog

        Example:
            rbt.jog_l("WRF", "X", speed=0.5, duration=1.0)
        """
        ...

    @abstractmethod
    async def wait_motion(
        self,
        timeout: float = 10.0,
        **kwargs: Any,
    ) -> bool:
        """Block until the robot has stopped moving or *timeout* expires.

        Category: Synchronization

        Example:
            rbt.wait_motion()
        """
        ...

    @abstractmethod
    async def wait_command(
        self,
        command_index: int,
        timeout: float = 10.0,
    ) -> bool:
        """Block until a specific command index has completed.

        Category: Synchronization

        Example:
            rbt.wait_command(<index>)
        """
        ...

    async def wait_status(
        self,
        predicate: Callable[[StatusBuffer], bool],
        timeout: float = 5.0,
    ) -> bool:
        """Block until *predicate* returns True for a status snapshot."""
        raise NotImplementedError

    async def wait_checkpoint(
        self,
        label: str,
        timeout: float = 30.0,
    ) -> bool:
        """Block until a checkpoint with *label* is reached."""
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> int:
        """Stop all motion — cancel the active move and clear the queue.

        The controller stays enabled and holding position; the next motion
        command is accepted immediately.

        Category: Control

        Example:
            rbt.stop()
        """
        ...

    @abstractmethod
    async def estop(self) -> int:
        """Protective stop: stop all motion and latch the controller
        disabled until ``reset()``.

        Category: Control

        Example:
            rbt.estop()
        """
        ...

    @abstractmethod
    async def reset(self) -> int:
        """Clear a latched protective stop, re-enabling motion.

        Category: Control

        Example:
            rbt.reset()
        """
        ...

    async def loop_stats(self) -> LoopStatsResult | None:
        """Control-loop runtime metrics; ``None`` when unreachable.

        Category: Query

        Example:
            stats = rbt.loop_stats()
        """
        raise NotImplementedError

    async def simulator(self, enabled: bool) -> int:
        """Enable or disable simulator mode.

        Category: Control

        Example:
            rbt.simulator(True)
        """
        raise NotImplementedError

    async def is_simulator(self) -> bool:
        """Query whether simulator mode is active.

        Category: Query

        Example:
            active = rbt.is_simulator()
        """
        raise NotImplementedError

    async def teleport(
        self,
        angles_deg: list[float],
        tool_positions: list[float] | None = None,
    ) -> int:
        """Instantly set joint angles and optional tool positions (simulator only).

        Category: Control

        Example:
            rbt.teleport([0, -90, 0, 0, 0, 0])
            rbt.teleport([0, -90, 0, 0, 0, 0], tool_positions=[1.0])
        """
        raise NotImplementedError

    async def freedrive(self, enabled: bool) -> int:
        """Release the arm for hand guiding, or take it back under control.

        How a backend delivers this is its own business — a gravity
        feedforward with no position term, a brake release, an impedance
        mode. Callers state the intent; the backend picks the mechanism,
        and refuses with its own reason when the arm is in no state to be
        pushed around (unreferenced joints, drives down, mid-move).

        Category: Control

        Example:
            rbt.freedrive(True)
        """
        raise NotImplementedError

    async def is_freedrive(self) -> bool:
        """Whether the arm is back-driveable right now.

        The question is about the arm, not the request: a backend that
        accepted ``freedrive(True)`` but cannot honour it yet answers
        False. Never report an arm safe to grab on the strength of a
        command having been sent.

        Category: Query

        Example:
            if rbt.is_freedrive():
                ...
        """
        raise NotImplementedError

    async def set_shapes(self, shapes: list[Shape]) -> int:
        """Replace the program-layer keep-out / marker shapes (the collision world).

        Collision-enabled shapes are added to the backend's collision checkers so
        motion is blocked against them; an empty list clears all program-layer
        shapes.  Installation-layer shapes (declared in the backend's robot
        config) are unaffected — programs inherit them and cannot remove them.

        The change also invalidates committed motion: the backend re-guards
        the currently-streaming trajectory's remaining path and every queued
        trajectory before it starts, halting with a collision error rather
        than driving into a keep-out declared after the motion was planned.

        Returns ``1`` only after the backend confirms the world was applied;
        ``0`` if unconfirmed, ``< 0`` if the backend rejected the shapes (see
        the class docstring's return-code convention).

        Category: Configuration

        Example:
            rbt.set_shapes([Box(name="table", x=0.6, y=0.4, z=0.02,
                                pose=(0.3, 0, -0.01, 0, 0, 0))])
        """
        raise NotImplementedError

    async def shapes(self) -> ShapeWorld | None:
        """The collision world the backend is currently enforcing, by layer.

        Readback truth: displays should render this — not a locally stored
        copy — re-querying whenever ``StatusBuffer.scene_epoch`` changes.
        Returns None if the backend is unreachable.

        Category: Query

        Example:
            world = rbt.shapes()
        """
        raise NotImplementedError

    @abstractmethod
    async def angles(self) -> list[float] | None:
        """Current joint angles in degrees.

        Category: Query

        Example:
            angles = rbt.angles()
        """
        ...

    @abstractmethod
    async def pose(self, frame: Frame = "WRF") -> list[float] | None:
        """Current TCP pose as [x, y, z, rx, ry, rz] in mm and degrees.

        Category: Query

        Example:
            pose = rbt.pose()
        """
        ...

    async def joint_speeds(self) -> list[float] | None:
        """Current joint velocities.

        Category: Query

        Example:
            speeds = rbt.joint_speeds()
        """
        raise NotImplementedError

    async def io(self) -> list[int] | None:
        """Digital I/O state.

        Category: Query

        Example:
            io = rbt.io()
        """
        raise NotImplementedError

    async def status(self) -> object | None:
        """Aggregate status snapshot.

        Category: Query

        Example:
            status = rbt.status()
        """
        raise NotImplementedError

    async def queue(self) -> list[str] | None:
        """Queued command list.

        Category: Query

        Example:
            queue = rbt.queue()
        """
        raise NotImplementedError

    async def tools(self) -> ToolResult | None:
        """Current tool and available tools.

        Category: Query

        Example:
            tools = rbt.tools()
        """
        raise NotImplementedError

    async def activity(self) -> ActivityResult | None:
        """What the robot is currently doing.

        Returns state (idle/executing/error), current command name,
        parameters, and error description if applicable.

        Category: Query

        Example:
            act = rbt.activity()
        """
        raise NotImplementedError

    async def reachable(self) -> object | None:
        """Remaining freedom of movement per joint/axis before hitting limits.

        Category: Query

        Example:
            en = rbt.reachable()
        """
        raise NotImplementedError

    async def error(self) -> object | None:
        """Current error state, or None if no error.

        Category: Query

        Example:
            err = rbt.error()
        """
        raise NotImplementedError

    async def profile(self) -> str | None:
        """Current motion profile name.

        Category: Query

        Example:
            profile = rbt.profile()
        """
        raise NotImplementedError

    async def tcp_speed(self) -> float | None:
        """TCP linear velocity in mm/s.

        Category: Query

        Example:
            speed = rbt.tcp_speed()
        """
        raise NotImplementedError

    async def connect_hardware(self, port_str: str) -> int:
        """Connect to robot hardware via serial port.

        Category: Configuration

        Example:
            rbt.connect_hardware("/dev/ttyUSB0")
        """
        raise NotImplementedError

    async def select_profile(self, profile: str) -> int:
        """Set the motion profile (e.g. ``"TOPPRA"``).

        Category: Configuration

        Example:
            rbt.select_profile("TOPPRA")
        """
        raise NotImplementedError

    async def select_tool(self, tool_name: str, variant_key: str = "") -> int:
        """Set the active end-effector tool on the controller.

        Category: Configuration

        Example:
            rbt.select_tool("PNEUMATIC")
        """
        raise NotImplementedError

    async def set_tcp_offset(self, x: float = 0, y: float = 0, z: float = 0) -> int:
        """Set TCP offset in mm, composed on top of the current tool transform.

        The offset shifts the effective TCP point in the tool's local frame.
        Subsequent motion (especially TRF relative moves) will use the new TCP.
        Call with (0, 0, 0) to reset. Changing tools resets the offset.

        Category: Configuration

        Example:
            rbt.set_tcp_offset(0, 0, -190)
        """
        raise NotImplementedError

    async def tcp_offset(self) -> list[float]:
        """Query current TCP offset in mm [x, y, z].

        Category: Configuration

        Example:
            offset = rbt.tcp_offset()
        """
        raise NotImplementedError

    async def set_payload(
        self,
        mass: float,
        com: tuple[float, float, float] = (0.0, 0.0, 0.0),
        inertia: Inertia6 | None = None,
    ) -> int:
        """Declare what the arm is carrying at the TCP.

        An inertial declaration only: the gravity feedforward and torque
        planning carry it, the collision geometry does not change (use
        ``set_shapes`` for that).

        This is what a backend's own model cannot know. A shipped model
        describes the nominal arm; the mass in the gripper, the fixture
        bolted to the flange and the spool on the end of it are the
        operator's, and they move the first moments the gravity model
        depends on.

        *mass* in kg, 0 clears the payload. *com* is the centre of mass in
        end-effector-frame metres. *inertia* is an :data:`Inertia6`;
        omitted means a point mass.

        Invalid input — a negative mass, an inertia that is not positive
        semidefinite — raises ``RuntimeError`` (a backend's own error type
        derives from it) rather than returning -1.

        Category: Configuration

        Example:
            rbt.set_payload(1.2, com=(0.0, 0.0, 0.05))
        """
        raise NotImplementedError

    async def estimate_payload(
        self,
        spread: float = 0.5,
        ridge: float = 0.01,
        declare: bool = True,
    ) -> PayloadEstimate:
        """Estimate what the arm is carrying, and declare it.

        Mass and centre of mass, from the torque the arm holds. NOT the
        inertia tensor: static poses cannot excite it, so the result is
        carried as a point mass — which is what most payloads are well
        enough described by. A payload whose inertia matters is declared
        with ``set_payload`` from its drawing.

        Call it after closing on a part whose mass is not known. **The
        arm moves**: the backend swings the wrist — where the load's
        lever arm is, so nothing below moves and the pick is not
        disturbed — through a few poses, taking seconds.

        The backend clears the declared payload before measuring (the
        load is found in the torque an *unloaded* model cannot explain)
        and restores it on every exit that does not declare, failure
        included. With *declare* (the default) the estimate replaces it,
        so the gravity model carries the part from the next tick.

        *spread* is how far each wrist joint swings either way, in
        radians. *ridge* holds back parameters the motion did not
        measure.

        Raises ``RuntimeError`` (a backend's own error type derives from
        it) when there is no room to measure, or when *declare* is set
        and no mass was actually measured — a backend must refuse rather
        than declare noise.

        Category: Motion

        Example:
            found = rbt.estimate_payload()
            print(f"holding {found.mass:.3f} kg")
        """
        raise NotImplementedError

    async def payload(self) -> PayloadResult | None:
        """The payload the runtime is currently carrying.

        Returns ``None`` if the backend is unreachable. A backend that
        carries no payload reports zeros rather than ``None``.

        Category: Query

        Example:
            print(rbt.payload())
        """
        raise NotImplementedError

    @property
    def tool(self) -> ToolSpec:
        """The active bound tool.

        Raises ``RuntimeError`` if no tool has been set.
        """
        raise NotImplementedError

    async def write_io(self, index: int, value: int) -> int:
        """Set digital output by logical index (0 = first output pin).

        Category: I/O

        Example:
            rbt.write_io(0, 1)   # Set first output HIGH
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

    async def reset_state(self) -> int:
        """Reset controller state (world shapes, tool selection, errors).

        Category: Control

        Example:
            rbt.reset_state()
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
