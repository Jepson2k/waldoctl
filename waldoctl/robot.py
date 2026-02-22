"""Robot ABC — the single entry point for any backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from waldoctl.client import RobotClient
from waldoctl.dry_run import DryRunClient
from waldoctl.joints import JointsSpec
from waldoctl.results import IKResult
from waldoctl.tools import ToolsSpec


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

    @property
    @abstractmethod
    def tools(self) -> ToolsSpec:
        """Available end-effector tools and their capabilities."""
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
    def fk(self, q_rad: NDArray[np.float64]) -> NDArray[np.float64]:
        """Forward kinematics.

        *q_rad*: joint angles in radians ``(num_joints,)``.

        Returns ``(6,)`` — ``[x, y, z, rx, ry, rz]`` in meters + radians.
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
    def create_client(self, **kwargs: Any) -> RobotClient:
        """Create an async client connected to this backend."""
        ...

    def create_dry_run_client(self, **kwargs: Any) -> DryRunClient | None:
        """Create an offline simulation client, or None if unsupported."""
        return None
