"""User-facing settings — jog / gripper / view / plugins.

Sub-objects (``JogSettings``, ``GripperSettings``, ``ViewSettings``,
``PluginConfig``) hold leaf preferences that the UI binds to directly.
``simulator_active`` lives at the top because it's a mode flag, not a pref.

**Mutate-in-place invariant**: sub-objects are constructed once and mutated;
never reassigned.
"""

from __future__ import annotations

from dataclasses import field
from enum import Enum

from nicegui import binding

from waldoctl.robot_status import ChangeNotifierMixin


# ---------------------------------------------------------------------------
# EnvelopeMode — workspace-envelope visibility tri-state
# ---------------------------------------------------------------------------


class EnvelopeMode(Enum):
    """Workspace envelope visibility modes."""

    AUTO = "auto"
    ON = "on"
    OFF = "off"


# ---------------------------------------------------------------------------
# Settings sub-objects
# ---------------------------------------------------------------------------


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
    preview_mode: bool = False
    """True = dry-run preview, False = real-hardware execute intent."""


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


# ---------------------------------------------------------------------------
# Settings — the locator's `settings` attribute
# ---------------------------------------------------------------------------


@binding.bindable_dataclass
class Settings(ChangeNotifierMixin):
    """User-facing preferences and configuration — the public ``commander.settings``.

    Sub-objects group preferences by domain (jog / gripper / view / plugins).
    UI sliders, switches, and dropdowns bind to leaf fields on the nested
    objects (``bind_value(commander.settings.jog, "speed")``).

    **Mutate-in-place invariant**: the sub-objects are constructed once and
    their fields are mutated; the sub-objects themselves are never swapped.
    """

    jog: JogSettings = field(default_factory=JogSettings)
    gripper: GripperSettings = field(default_factory=GripperSettings)
    view: ViewSettings = field(default_factory=ViewSettings)
    plugins: PluginConfig = field(default_factory=PluginConfig)
    simulator_active: bool = False
