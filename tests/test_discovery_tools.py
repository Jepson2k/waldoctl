"""Tests for ``waldoctl.discovery`` tool-spec helpers and StrEnum tool type."""

from __future__ import annotations

import pytest

from tests.conftest import install_fake_entry_points
from waldoctl import ToolsCollection, ToolSpec, ToolType
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
    """Install fake ``waldoctl.tools`` entry points for *mapping*."""
    install_fake_entry_points(monkeypatch, "waldoctl.tools", mapping)


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


class _Gripperish(ToolSpec):
    """Concrete tool in the GRIPPER category — the shipped gripper classes are
    abstract, and this test only needs something that carries the category."""

    def __init__(self) -> None:
        super().__init__(
            key="pneumatic_left",
            display_name="Left",
            tool_type=ToolType.GRIPPER,
            tcp_origin=(0.0, 0.0, 0.0),
            tcp_rpy=(0.0, 0.0, 0.0),
        )


def test_membership_routes_a_category_and_a_key_to_different_lookups():
    """``ToolType`` is a ``StrEnum``, so an ``isinstance(item, str)`` branch
    tested first would swallow a category and answer it against the key
    table — every category lookup returning False. The source orders the
    branches to avoid exactly that; this is what pins the ordering.
    """
    laser = _LaserTool()  # keyed "laser", typed "laser"
    grip = _Gripperish()  # keyed "pneumatic_left", typed GRIPPER
    tools = ToolsCollection((laser, grip))

    # Keys are canonicalised to strip+upper on construction so a plugin tool
    # registered lowercase is still selectable, which is why the lookup is
    # against "LASER" and not the "laser" it was declared with.
    assert "LASER" in tools, "a key resolves through the key table"
    assert "laser" not in tools, "the key table holds the canonical form"
    assert "gripper" not in tools, "a category name is not a key"
    assert ToolType.GRIPPER in tools, "the category matches by tool_type"
    assert ToolType.NONE not in tools, "no tool carries this category"

    assert tools.by_type(ToolType.GRIPPER) == (grip,)
    assert tools.by_type("laser") == (laser,), "a plain str category still works"
