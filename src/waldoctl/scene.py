"""``SceneHandle`` — a plugin's window into the host's shared 3D scene.

Exposed as ``commander.scene`` (``None`` on hosts without a 3D scene — plugins
must guard). Plugins draw into a named, plugin-owned group so their geometry
(PCB board, height-map, scan path, markers) sits in the same world as the robot
without a second ``ui.scene`` or touching host internals.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol

from waldoctl.shapes import Shape


class SceneHandle(Protocol):
    shapes: list[Shape]
    """Workspace keep-out / marker shapes (the collision world). **Reassign the
    whole list** (``scene.shapes = [*scene.shapes, box]``) — in-place mutation
    (``.append``) is invisible to the host. On reassignment the host renders the
    shapes and pushes the collision-enabled ones to the backend's checkers
    (``commander.client.set_shapes`` is the underlying command)."""

    def overlay(self, group_id: str) -> AbstractContextManager[Any]:
        """Batched context yielding the 3D scene to draw on; replaces *group_id*'s
        prior contents on entry.

        ``group_id`` is a **global** namespace shared by every plugin on the one
        scene — pick a unique id (e.g. prefix with your ``Panel.id``) so two
        plugins don't clobber each other's overlay. Safely no-ops (yields a null
        scene) when no 3D scene is connected or it has been torn down.
        """
        ...

    def clear(self, group_id: str) -> None:
        """Remove a plugin-owned group's contents."""
        ...
