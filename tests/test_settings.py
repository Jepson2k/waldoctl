"""Tests for ``Settings`` and its sub-objects (jog / gripper / view / plugins)."""

from __future__ import annotations

from nicegui import binding

from waldoctl import (
    EnvelopeMode,
    Settings,
)


class _Target:
    value: object = None


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
