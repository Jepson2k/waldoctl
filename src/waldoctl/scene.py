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
    def enforced_locally(self) -> list[Shape]:
        """Everything this process's own collision checker holds: the
        program layer plus the installation proposal.

        The proposal is enforced nowhere else until the backend's robot
        config declares it, so a preview or an editing-pose query that
        wants to see it must ask for this rather than for
        :attr:`shapes`.
        """
        ...

    @property
    def installation_draft(self) -> tuple[Shape, ...]:
        """Shapes proposed for the installation layer.

        A proposal leaves the layer the backend enforces and is checked by
        this process instead — local collision queries and the dry run see
        it, so a layout can be flown against before it is committed — until
        the robot config declares it, which the host exports as that
        config's TOML. A proposal clears itself when readback shows the
        backend enforcing it.
        """
        ...

    def propose_installation(self, names: list[str]) -> None:
        """Move the named program-layer shapes into the installation draft."""
        ...

    def discard_installation_draft(self, names: list[str] | None = None) -> None:
        """Drop the named draft shapes (all when *names* is None)."""
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
