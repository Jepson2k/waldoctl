"""Pluggable GUI panel interface for waldoctl frontends.

Third-party packages register additional tabs by subclassing :class:`Panel`
and listing the subclass under the ``waldoctl.panels`` entry-point group::

    [project.entry-points."waldoctl.panels"]
    notes = "mypackage.notes:NotesPanel"

The frontend (e.g. Waldo-Commander) discovers panels via
:func:`waldoctl.discovery.iter_plugin_panels`, filters by
:meth:`Panel.applies_to`, and renders each panel in its declared slot.

This module is intentionally NiceGUI-free — waldoctl stays import-light.
Plugin implementations import their UI toolkit themselves inside
:meth:`Panel.build`.

Panels receive the live :class:`~waldoctl.Commander` directly. Through
``commander`` the panel reaches the robot, client, live status, programs,
and settings — the same public surface every other consumer uses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from waldoctl._commander import Commander


class PanelSlot(str, Enum):
    """Where a plugin panel attaches in the frontend layout."""

    LEFT_TOP_TAB = "left-top-tab"
    """Alongside core top-left tabs (program / io / gripper)."""
    LEFT_BOTTOM_TAB = "left-bottom-tab"
    """Alongside core bottom-left tabs (log / help)."""


class Panel(ABC):
    """Base class for a pluggable frontend tab.

    Subclasses set the class-level metadata (``id``, ``display_name``,
    ``slot``) and override :meth:`build`. The remaining hooks are
    optional — override only what the panel needs.
    """

    id: ClassVar[str]
    display_name: ClassVar[str]
    slot: ClassVar[PanelSlot]
    tab_icon: ClassVar[str | None] = None
    tab_tooltip: ClassVar[str | None] = None
    order: ClassVar[int] = 100

    def applies_to(self, commander: Commander) -> bool:
        """Return False to suppress the tab for this robot/session."""
        return True

    @abstractmethod
    def build(self, commander: Commander) -> None:
        """Build UI elements inside the frontend's active tab container."""

    async def start(self, commander: Commander) -> None:
        """Spawn long-running tasks. Called after the page is built."""

    async def stop(self) -> None:
        """Cancel/await tasks started in :meth:`start`. Called on shutdown."""
