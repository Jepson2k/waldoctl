"""Tests for ``waldoctl.discovery`` panel helpers."""

from __future__ import annotations

import importlib.metadata
from typing import ClassVar

import pytest

from waldoctl import Panel, PanelSlot
from waldoctl.discovery import (
    iter_plugin_panels,
    list_panels,
    load_panel_class,
)


class _NotesPanel(Panel):
    id: ClassVar[str] = "notes"
    display_name: ClassVar[str] = "Notes"
    slot: ClassVar[PanelSlot] = PanelSlot.LEFT_TOP_TAB

    def build(self, commander: object) -> None:
        pass


class _NotAPanel:
    """Decoy class that is not a Panel subclass."""


class _NoIdPanel(Panel):
    """Malformed panel: a Panel subclass that never sets the required ``id``."""

    display_name: ClassVar[str] = "No Id"
    slot: ClassVar[PanelSlot] = PanelSlot.LEFT_TOP_TAB

    def build(self, commander: object) -> None:
        pass


def _fake_entry_points(
    monkeypatch: pytest.MonkeyPatch, mapping: dict[str, object]
) -> None:
    """Install ``importlib.metadata.entry_points`` returning *mapping* for the
    ``waldoctl.panels`` group."""

    real = importlib.metadata.entry_points

    def fake(*, group: str = "") -> list[importlib.metadata.EntryPoint]:
        if group != "waldoctl.panels":
            return real(group=group) if group else real()
        eps = []
        for name, target in mapping.items():
            eps.append(
                importlib.metadata.EntryPoint(
                    name=name,
                    value=f"{target.__module__}:{target.__qualname__}",
                    group="waldoctl.panels",
                )
            )
        return eps

    monkeypatch.setattr(importlib.metadata, "entry_points", fake)


def test_list_panels_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_entry_points(monkeypatch, {})
    assert list_panels() == {}
    assert iter_plugin_panels() == []


def test_iter_plugin_panels_returns_subclass(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_entry_points(monkeypatch, {"notes": _NotesPanel})
    panels = iter_plugin_panels()
    assert panels == [_NotesPanel]


def test_load_panel_class_missing_raises_lookuperror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_entry_points(monkeypatch, {})
    with pytest.raises(LookupError):
        load_panel_class("missing")


def test_load_panel_class_wrong_type_raises_typeerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_entry_points(monkeypatch, {"bad": _NotAPanel})
    with pytest.raises(TypeError):
        load_panel_class("bad")


def test_iter_plugin_panels_skips_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_entry_points(monkeypatch, {"bad": _NotAPanel, "notes": _NotesPanel})
    assert iter_plugin_panels() == [_NotesPanel]


def test_iter_plugin_panels_skips_typoed_attribute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An entry point whose module imports but whose class attribute is missing
    (a typo) raises AttributeError on load; it must be skipped, not abort the
    other panels."""
    real = importlib.metadata.entry_points

    def fake(*, group: str = "") -> list[importlib.metadata.EntryPoint]:
        if group != "waldoctl.panels":
            return real(group=group) if group else real()
        return [
            importlib.metadata.EntryPoint(
                name="typo", value=f"{__name__}:NoSuchPanel", group="waldoctl.panels"
            ),
            importlib.metadata.EntryPoint(
                name="notes",
                value=f"{_NotesPanel.__module__}:{_NotesPanel.__qualname__}",
                group="waldoctl.panels",
            ),
        ]

    monkeypatch.setattr(importlib.metadata, "entry_points", fake)
    assert iter_plugin_panels() == [_NotesPanel]


def test_iter_plugin_panels_skips_missing_classvars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A Panel subclass that never sets the required `id` ClassVar is malformed;
    # it is skipped so downstream `cls.id` access is guard-free.
    _fake_entry_points(monkeypatch, {"noid": _NoIdPanel, "notes": _NotesPanel})
    assert iter_plugin_panels() == [_NotesPanel]


def test_panel_defaults() -> None:
    panel = _NotesPanel()
    assert panel.applies_to(None) is True  # type: ignore[arg-type]
    assert panel.order == 100
    assert panel.tab_icon is None
