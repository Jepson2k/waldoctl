"""Robot ABC — the single entry point for any backend."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from waldoctl.client import RobotClient
from waldoctl.discovery import iter_plugin_tool_specs
from waldoctl.dry_run import DryRunClient
from waldoctl.joints import CartesianKinodynamicLimits, JointsSpec
from waldoctl.results import IKResult
from waldoctl.shapes import Shape
from waldoctl.tools import ComposedToolsSpec, ToolsSpec

logger = logging.getLogger(__name__)


def _compose_plugin_tools(native: ToolsSpec) -> ToolsSpec:
    """Compose *native* backend tools with plugin tools from ``waldoctl.tools``."""
    plugin_specs = iter_plugin_tool_specs()
    if not plugin_specs:
        return native
    logger.info(
        "Loaded %d plugin tool(s) via waldoctl.tools: %s",
        len(plugin_specs),
        [t.key for t in plugin_specs],
    )
    return ComposedToolsSpec(native, tuple(plugin_specs))


class Robot(ABC):
    """Unified robot interface — the single entry point for any backend.

    Combines identity, joint configuration, tool definitions, kinematics,
    lifecycle management, and client factories into one ABC.

    Required methods are marked with ``@abstractmethod``.  Optional
    capabilities have concrete defaults that backends override as needed.
    """

    # -- Identity -----------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable robot name, e.g. ``"PAROL6"``."""
        ...

    # -- Structured sub-objects ---------------------------------------------

    @property
    @abstractmethod
    def joints(self) -> JointsSpec:
        """Joint configuration: count, names, limits, home position."""
        ...

    _tools_composed: ToolsSpec | None = None

    @property
    def tools(self) -> ToolsSpec:
        """Backend-native tools composed with plugins registered via
        ``waldoctl.tools``. Cached per instance (entry points are static)."""
        if self._tools_composed is None:
            self._tools_composed = _compose_plugin_tools(self.native_tools)
        return self._tools_composed

    @property
    @abstractmethod
    def native_tools(self) -> ToolsSpec:
        """The backend's own tools; composed with plugin tools by :attr:`tools`.

        Backends implement this; consumers read :attr:`tools` (which adds plugin
        tools)."""
        ...

    @property
    @abstractmethod
    def cartesian_limits(self) -> CartesianKinodynamicLimits:
        """Jog-mode Cartesian velocity and acceleration limits."""
        ...

    # -- Unit preferences ---------------------------------------------------

    @property
    @abstractmethod
    def position_unit(self) -> Literal["mm", "m"]:
        """How this robot's users think about distance (display hint)."""
        ...

    # -- Capability flags ---------------------------------------------------

    @property
    def has_force_torque(self) -> bool:
        """Whether force / torque readout is available."""
        return False

    @property
    def has_freedrive(self) -> bool:
        """Whether a freedrive / teach mode is available."""
        return False

    @property
    @abstractmethod
    def digital_outputs(self) -> int:
        """Number of digital output pins."""
        ...

    @property
    @abstractmethod
    def digital_inputs(self) -> int:
        """Number of digital input pins."""
        ...

    # -- Visualization ------------------------------------------------------

    @property
    @abstractmethod
    def urdf_path(self) -> str:
        """Path to the URDF file for 3-D rendering."""
        ...

    @property
    @abstractmethod
    def mesh_dir(self) -> str:
        """Directory containing STL / mesh files referenced by the URDF."""
        ...

    @property
    @abstractmethod
    def joint_index_mapping(self) -> tuple[int, ...]:
        """Maps URDF joint indices to control joint indices."""
        ...

    # -- Motion configuration -----------------------------------------------

    @property
    def motion_profiles(self) -> tuple[str, ...]:
        """Available motion profile names.

        At least one profile is required.  The default is ``("linear",)``
        which backends should override with their actual profiles.
        """
        return ("linear",)

    @property
    def cartesian_frames(self) -> tuple[str, ...]:
        """Available Cartesian reference frames for jogging.

        Default includes both WRF and TRF which are required.
        """
        return ("WRF", "TRF")

    # -- Backend injection --------------------------------------------------

    @property
    @abstractmethod
    def backend_package(self) -> str:
        """Python package used by user scripts and subprocess workers."""
        ...

    @property
    @abstractmethod
    def sync_client_class(self) -> type:
        """The synchronous client class (e.g. ``RobotClient``).

        Used for editor autocomplete discovery and stepping wrapper.
        Convention: backends export this class at their package level.
        """
        ...

    @property
    @abstractmethod
    def async_client_class(self) -> type:
        """The asynchronous client class (e.g. ``AsyncRobotClient``).

        Used for editor command discovery (introspecting available methods).
        Convention: backends export this class at their package level.
        """
        ...

    # -- Kinematics ---------------------------------------------------------

    @abstractmethod
    def fk(
        self, q_rad: NDArray[np.float64], out: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        """Forward kinematics.

        *q_rad*: joint angles in radians ``(num_joints,)``.
        *out*: pre-allocated ``(6,)`` buffer to write the result into.

        Returns *out* filled with ``[x, y, z, rx, ry, rz]`` in meters + radians.
        """
        ...

    @abstractmethod
    def ik(
        self, pose: NDArray[np.float64], q_seed_rad: NDArray[np.float64]
    ) -> IKResult:
        """Inverse kinematics.

        *pose*: ``[x, y, z, rx, ry, rz]`` — meters + radians.
        *q_seed_rad*: current joint angles in radians (seed).

        Returns an ``IKResult`` with ``q`` in radians.
        """
        ...

    @abstractmethod
    def set_active_tool(
        self,
        tool_key: str,
        tcp_offset_m: tuple[float, float, float] | None = None,
        variant_key: str | None = None,
    ) -> None:
        """Apply tool transform to the local FK/IK model.

        When set, ``fk()`` returns TCP position instead of flange position.

        *tcp_offset_m*: optional (x, y, z) user offset in meters, composed
        on top of the tool's registered transform.
        *variant_key*: optional variant whose TCP overrides the tool default.
        """
        ...

    @abstractmethod
    def check_limits(self, q_rad: NDArray[np.float64]) -> bool:
        """Return ``True`` if all joints are within limits."""
        ...

    @abstractmethod
    def fk_batch(self, joint_path_rad: NDArray[np.float64]) -> NDArray[np.float64]:
        """Batch FK: ``(N, num_joints)`` radians -> ``(N, 6)`` poses (m + rad)."""
        ...

    @abstractmethod
    def ik_batch(
        self,
        poses: NDArray[np.float64],
        q_start_rad: NDArray[np.float64],
    ) -> list[IKResult]:
        """Batch IK: ``(N, 6)`` poses -> list of ``IKResult`` (radians)."""
        ...

    # -- Collision (concrete disabled-defaults; backends with a checker override) -

    @property
    def has_collision_checking(self) -> bool:
        """Whether collision checking (self + workspace shapes) is available."""
        return False

    def in_collision(self, q_rad: NDArray[np.float64]) -> bool:
        """Whether ``q_rad`` (radians) collides — with itself, the attached
        tool, or a workspace keep-out shape."""
        return False

    def colliding_pairs(self, q_rad: NDArray[np.float64]) -> list[tuple[str, str]]:
        """Colliding (name, name) geometry/link pairs at ``q_rad``."""
        return []

    def check_trajectory(self, q_path_rad: NDArray[np.float64]) -> int:
        """First colliding row index in ``(N, num_joints)`` path, or -1 if clear."""
        return -1

    def min_distance(self, q_rad: NDArray[np.float64]) -> float:
        """Min clearance at ``q_rad`` (signed; negative = penetration)."""
        return float("inf")

    def apply_shapes(self, shapes: list[Shape]) -> None:
        """Apply workspace keep-out shapes to this process's local checker.

        Local-only twin of ``RobotClient.set_shapes`` (which updates the
        *backend's* checkers) — feeds client-side preview / editing-pose
        collision queries. No-op on backends without collision checking.
        """

    # -- Lifecycle ----------------------------------------------------------

    @abstractmethod
    def start(self, **kwargs: Any) -> None:
        """Start the backend process / connection (blocking).

        What "start" means is backend-specific: spawn a subprocess,
        connect to a remote server, launch a ROS node, etc.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the backend process and release resources."""
        ...

    @abstractmethod
    def is_available(self, **kwargs: Any) -> bool:
        """Check if the backend is reachable / ready."""
        ...

    # -- Factories ----------------------------------------------------------

    @abstractmethod
    def create_async_client(self, **kwargs: Any) -> RobotClient:
        """Create an async client connected to this backend."""
        ...

    @abstractmethod
    def create_sync_client(self, **kwargs: Any) -> object:
        """Create a synchronous client. Returns backend-specific type."""
        ...

    def create_dry_run_client(self, **kwargs: Any) -> DryRunClient | None:
        """Create an offline simulation client, or None if unsupported."""
        return None
