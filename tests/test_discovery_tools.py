"""Tests for ``waldoctl.discovery`` tool-spec helpers and StrEnum tool type."""

from __future__ import annotations

import importlib.metadata

import pytest

from waldoctl import ToolSpec, ToolType
from waldoctl.discovery import list_tool_specs, load_tool_spec_class


class _LaserTool(ToolSpec):
    def __init__(self) -> None:
        super().__init__(
            key="laser",
            display_name="Laser",
            tool_type="laser",
            tcp_origin=(0.0, 0.0, 0.0),
            tcp_rpy=(0.0, 0.0, 0.0),
        )


class _NotATool:
    """Decoy class that is not a ToolSpec subclass."""


def _fake_entry_points(
    monkeypatch: pytest.MonkeyPatch, mapping: dict[str, object]
) -> None:
    real = importlib.metadata.entry_points

    def fake(*, group: str = "") -> list[importlib.metadata.EntryPoint]:
        if group != "waldoctl.tools":
            return real(group=group) if group else real()
        eps = []
        for name, target in mapping.items():
            eps.append(
                importlib.metadata.EntryPoint(
                    name=name,
                    value=f"{target.__module__}:{target.__qualname__}",
                    group="waldoctl.tools",
                )
            )
        return eps

    monkeypatch.setattr(importlib.metadata, "entry_points", fake)


def test_list_tool_specs_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_entry_points(monkeypatch, {})
    assert list_tool_specs() == {}


def test_load_tool_spec_missing_raises_lookuperror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_entry_points(monkeypatch, {})
    with pytest.raises(LookupError):
        load_tool_spec_class("missing")


def test_load_tool_spec_wrong_type_raises_typeerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_entry_points(monkeypatch, {"bad": _NotATool})
    with pytest.raises(TypeError):
        load_tool_spec_class("bad")


def test_load_tool_spec_class_returns_subclass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_entry_points(monkeypatch, {"laser": _LaserTool})
    cls = load_tool_spec_class("laser")
    assert cls is _LaserTool


def test_tooltype_is_strenum() -> None:
    """``ToolType.GRIPPER == "gripper"`` so backends can pass strings safely."""
    assert issubclass(ToolType, str)
    assert ToolType.GRIPPER == "gripper"
    assert ToolType.NONE == "none"


def test_third_party_tool_type_string() -> None:
    """``ToolSpec`` accepts arbitrary tool-type strings beyond the built-in enum."""
    tool = _LaserTool()
    assert tool.tool_type == "laser"
