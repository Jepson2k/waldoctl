"""``SceneHandle`` — a plugin's window into the host's shared 3D scene.

Exposed as ``commander.scene`` (``None`` on hosts without a 3D scene — plugins
must guard). Plugins draw into a named, plugin-owned group so their geometry
(PCB board, height-map, scan path, markers) sits in the same world as the robot
without a second ``ui.scene`` or touching host internals.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol


class SceneHandle(Protocol):
    def overlay(self, group_id: str) -> AbstractContextManager[Any]:
        """Batched context yielding the 3D scene to draw on; replaces *group_id*'s
        prior contents on entry."""
        ...

    def clear(self, group_id: str) -> None:
        """Remove a plugin-owned group's contents."""
        ...
