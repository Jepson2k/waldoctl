"""Tests for the ToolSpec camera + runtime-settings extension."""

from __future__ import annotations

import dataclasses

import pytest
from nicegui import binding

from waldoctl import CameraSpec, ToolRuntimeSettings, ToolStatus
from waldoctl.tools import ToolSpec, ToolType


class _StubTool(ToolSpec):
    """Minimal concrete ToolSpec usable in tests."""

    async def action_l(self, engaged: bool) -> None:
        return None

    async def action_r(self, engaged: bool) -> None:
        return None

    async def status(self) -> ToolStatus:
        return ToolStatus()


class _Target:
    value: object = None


def _build_tool(*, camera_spec: CameraSpec | None = None) -> _StubTool:
    return _StubTool(
        key="STUB",
        display_name="Stub",
        tool_type=ToolType.NONE,
        tcp_origin=(0.0, 0.0, 0.0),
        tcp_rpy=(0.0, 0.0, 0.0),
        camera_spec=camera_spec,
    )


# ---------------------------------------------------------------------------
# CameraSpec
# ---------------------------------------------------------------------------


def test_camera_spec_is_frozen():
    c = CameraSpec(device=3)
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.device = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ToolRuntimeSettings
# ---------------------------------------------------------------------------


def test_runtime_settings_is_bindable():
    rs = ToolRuntimeSettings()
    t = _Target()
    binding.bind_from(t, "value", rs, "camera_device", backward=lambda v: v)
    rs.camera_device = 7
    assert t.value == 7
    rs.camera_device = "/dev/video2"
    assert t.value == "/dev/video2"


# ---------------------------------------------------------------------------
# ToolSpec integration
# ---------------------------------------------------------------------------


def test_tool_carries_camera_spec_when_provided():
    cs = CameraSpec(device=3, width=640, height=480)
    t = _build_tool(camera_spec=cs)
    assert t.camera_spec is cs


def test_tool_camera_spec_defaults_to_none():
    t = _build_tool()
    assert t.camera_spec is None


def test_tool_has_per_instance_runtime_settings():
    a = _build_tool()
    b = _build_tool()
    assert a.runtime_settings is not b.runtime_settings


def test_effective_camera_device_uses_spec_default():
    t = _build_tool(camera_spec=CameraSpec(device=3))
    assert t.effective_camera_device == 3


def test_effective_camera_device_runtime_overrides_spec():
    t = _build_tool(camera_spec=CameraSpec(device=3))
    t.runtime_settings.camera_device = 7
    assert t.effective_camera_device == 7
    t.runtime_settings.camera_device = "/dev/video2"
    assert t.effective_camera_device == "/dev/video2"


def test_effective_camera_device_clear_override_returns_to_spec():
    t = _build_tool(camera_spec=CameraSpec(device=3))
    t.runtime_settings.camera_device = 7
    t.runtime_settings.camera_device = None
    assert t.effective_camera_device == 3


def test_effective_camera_device_bare_tool_with_no_spec_or_override():
    t = _build_tool()
    assert t.effective_camera_device is None


def test_effective_camera_device_bare_tool_with_runtime_override():
    """A tool with no spec-time camera_spec can still gain a runtime override —
    useful for the workspace-observer-on-NONE-tool workflow."""
    t = _build_tool()
    t.runtime_settings.camera_device = 9
    assert t.effective_camera_device == 9
