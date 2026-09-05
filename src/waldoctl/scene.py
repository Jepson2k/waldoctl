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
    """Program-layer keep-out / marker shapes (the collision world). **Reassign
    the whole list** (``scene.shapes = [*scene.shapes, box]``) — in-place
    mutation (``.append``) is invisible to the host. Reassignment is a request:
    the host renders it as a draft, pushes it with the acknowledged
    ``commander.client.set_shapes``, and confirms it against backend readback."""

    @property
    def installation(self) -> tuple[Shape, ...]:
        """Installation-layer shapes (backend robot config) per last readback."""
        ...

    @property
    def floor_z_m(self) -> float | None:
        """The installation floor height per last readback (``ShapeWorld.floor_z_m``);
        None when the backend models no floor."""
        ...

    @property
    def confirmed(self) -> bool:
        """Whether the displayed program layer matches backend readback."""
        ...

    def render(self) -> None:
        """(Re)draw the shape layers on the live scene (no-op without one)."""
        ...

    async def refresh_from_backend(self) -> None:
        """Adopt the backend's applied collision world (readback truth) for the
        display and the local preview checker."""
        ...

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
