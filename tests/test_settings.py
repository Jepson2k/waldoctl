"""Tests for ``Settings`` and its sub-objects (jog / gripper / view / plugins)."""

from __future__ import annotations

from nicegui import binding

from waldoctl import (
    EnvelopeMode,
    GripperSettings,
    JogSettings,
    McpSettings,
    PluginConfig,
    Settings,
    ViewSettings,
)


class _Target:
    value: object = None


def test_settings_defaults_are_safe():
    s = Settings()
    assert isinstance(s.jog, JogSettings)
    assert isinstance(s.gripper, GripperSettings)
    assert isinstance(s.view, ViewSettings)
    assert isinstance(s.plugins, PluginConfig)
    assert isinstance(s.mcp, McpSettings)
    assert s.simulator_active is False


def test_jog_settings_defaults():
    j = JogSettings()
    assert j.speed == 50
    assert j.accel == 50
    assert j.incremental is False
    assert j.joint_step_deg == 1.0


def test_gripper_settings_defaults():
    g = GripperSettings()
    assert g.speed_sync is True
    assert g.speed == 50
    assert g.current == 500
    assert g.target_position == 0.0


def test_view_settings_defaults():
    v = ViewSettings()
    assert v.gizmo_visible is True
    assert v.paths_visible is True
    assert v.envelope_mode is EnvelopeMode.AUTO
    assert v.preview_mode is False


def test_plugin_config_defaults():
    p = PluginConfig()
    assert p.backend is None
    assert p.disabled_panels == []


def test_envelope_mode_values():
    assert EnvelopeMode.AUTO.value == "auto"
    assert EnvelopeMode.ON.value == "on"
    assert EnvelopeMode.OFF.value == "off"


def test_binding_through_jog_settings():
    s = Settings()
    t = _Target()
    binding.bind_from(t, "value", s.jog, "speed", backward=lambda v: v)
    assert t.value == 50
    s.jog.speed = 20
    assert t.value == 20


def test_binding_through_view_settings_enum():
    s = Settings()
    t = _Target()
    binding.bind_from(t, "value", s.view, "envelope_mode", backward=lambda m: m.value)
    s.view.envelope_mode = EnvelopeMode.OFF
    assert t.value == "off"


def test_plugin_config_disabled_panels_replacement():
    s = Settings()
    t = _Target()
    binding.bind_from(t, "value", s.plugins, "disabled_panels", backward=tuple)
    s.plugins.disabled_panels = ["acme.notes", "foo.bar"]
    assert t.value == ("acme.notes", "foo.bar")


def test_plugin_config_backend_assignment():
    s = Settings()
    s.plugins.backend = "parol6"
    assert s.plugins.backend == "parol6"
    s.plugins.backend = None
    assert s.plugins.backend is None


def test_mcp_settings_defaults_are_off_and_safe():
    m = McpSettings()
    assert m.enabled is False  # opt-in
    assert m.host == "127.0.0.1"  # loopback only by default
    assert m.port == 7400
    assert m.auth_token is None
    assert m.allow_motion is True


def test_binding_through_mcp_settings_enabled():
    s = Settings()
    t = _Target()
    binding.bind_from(t, "value", s.mcp, "enabled", backward=lambda v: v)
    assert t.value is False
    s.mcp.enabled = True
    assert t.value is True


def test_mcp_settings_allow_motion_live_toggle():
    s = Settings()
    assert s.mcp.allow_motion is True
    s.mcp.allow_motion = False
    assert s.mcp.allow_motion is False
