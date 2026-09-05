"""User-facing settings — jog / gripper / view / plugins / mcp.

Sub-objects (``JogSettings``, ``GripperSettings``, ``ViewSettings``,
``PluginConfig``, ``McpSettings``) hold leaf preferences that the UI binds to
directly.

**Mutate-in-place invariant**: sub-objects are constructed once and mutated;
never reassigned.
"""

from __future__ import annotations

from dataclasses import field
from enum import Enum

from nicegui import binding

from waldoctl.notify import ChangeNotifierMixin


class EnvelopeMode(Enum):
    """Workspace envelope visibility modes."""

    AUTO = "auto"
    ON = "on"
    OFF = "off"


@binding.bindable_dataclass
class JogSettings(ChangeNotifierMixin):
    """Jog control preferences. UI sliders bind to these fields directly."""

    speed: int = 50
    """Joint jog speed, percent (0..100)."""
    accel: int = 50
    """Joint jog acceleration, percent (0..100)."""
    incremental: bool = False
    """True = stepped move (one click → one step); False = continuous while held."""
    joint_step_deg: float = 1.0
    """Degrees per step when incremental is True."""


@binding.bindable_dataclass
class GripperSettings(ChangeNotifierMixin):
    """Gripper UI preferences."""

    speed_sync: bool = True
    """Link gripper speed to jog speed."""
    speed: int = 50
    """Independent gripper speed when not synced, percent (0..100)."""
    current: int = 500
    """Gripper current limit (mA, electric grippers only)."""
    target_position: float = 0.0
    """User-set position target (0..1)."""


@binding.bindable_dataclass
class ViewSettings(ChangeNotifierMixin):
    """3D scene visualization preferences."""

    gizmo_visible: bool = True
    """Show the interactive transform gizmo in the scene."""
    paths_visible: bool = True
    """Show trajectory paths in the scene."""
    envelope_mode: EnvelopeMode = EnvelopeMode.AUTO
    """Workspace envelope visibility (AUTO / ON / OFF)."""
    divergence_visible: bool = True
    """Show the achieved path beside the planned one, where a backend
    simulates. The two differ by servo lag and gravity sag, and seeing
    where they part is the reason to simulate at all."""
    contacts_visible: bool = False
    """Show contact points and force arrows from the simulated run."""
    com_visible: bool = False
    """Show the simulated scene's centre of mass and its drop line."""


@binding.bindable_dataclass
class PluginConfig(ChangeNotifierMixin):
    """Runtime selection of which backend and which panel plugins are active.

    Persisted by the host application to its general key/value storage
    (``nicegui.app.storage.general``) so users can switch backends and toggle
    plugins on/off without reinstalling.
    """

    backend: str | None = None
    """Name of the backend chosen for next startup. ``None`` falls back to the
    single installed default; ambiguous-with-multiple-installed → startup
    chooser."""
    disabled_panels: list[str] = field(default_factory=list)
    """Plugin ids the user has turned off. Panel discovery skips these."""


@binding.bindable_dataclass
class McpSettings(ChangeNotifierMixin):
    """MCP (Model Context Protocol) server configuration.

    The host application starts a FastMCP server when ``enabled`` is True,
    exposing the public ``commander.*`` surface as MCP tools so an LLM
    client (Claude Desktop, etc.) can drive the robot. ``enabled``, ``host``,
    and ``port`` bind at server start — changing them needs a restart.

    Hardware-motion safety is enforced by the host's per-session GUI consent
    gate (the first real move of an MCP session needs a human OK), not a
    persistent toggle.
    """

    enabled: bool = False
    """Off by default — opting in surfaces the public API to outside clients."""
    host: str = "127.0.0.1"
    """Loopback by default; set to a LAN address (or ``0.0.0.0``) to let other
    machines on a trusted network reach the server."""
    port: int = 7400
    """Streamable-HTTP port the FastMCP server listens on."""


# ---------------------------------------------------------------------------
# Settings — the locator's `settings` attribute
# ---------------------------------------------------------------------------


@binding.bindable_dataclass
class Settings(ChangeNotifierMixin):
    """User-facing preferences and configuration — the public ``commander.settings``.

    Sub-objects group preferences by domain (jog / gripper / view / plugins /
    mcp). UI sliders, switches, and dropdowns bind to leaf fields on the nested
    objects (``bind_value(commander.settings.jog, "speed")``).

    **Mutate-in-place invariant**: the sub-objects are constructed once and
    their fields are mutated; the sub-objects themselves are never swapped.
    """

    jog: JogSettings = field(default_factory=JogSettings)
    gripper: GripperSettings = field(default_factory=GripperSettings)
    view: ViewSettings = field(default_factory=ViewSettings)
    plugins: PluginConfig = field(default_factory=PluginConfig)
    mcp: McpSettings = field(default_factory=McpSettings)
