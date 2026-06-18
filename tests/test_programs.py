"""Tests for ``Program`` / ``ProgramTabs`` and the program sub-objects."""

from __future__ import annotations

import time

import pytest

from waldoctl import (
    LogEntry,
    Program,
    ProgramLog,
    ProgramTabs,
)


# ---------------------------------------------------------------------------
# Program
# ---------------------------------------------------------------------------


def test_program_is_dirty_tracks_source_vs_saved():
    p = Program()
    assert p.is_dirty is False
    p.source = "rbt.home()\n"
    assert p.is_dirty is True
    p.mark_saved()
    assert p.is_dirty is False
    p.source = "rbt.home()\nrbt.move_l([0,0,0,0,0,0])\n"
    assert p.is_dirty is True


def test_program_ids_are_unique():
    a = Program()
    b = Program()
    assert a.id != b.id


# ---------------------------------------------------------------------------
# ProgramLog
# ---------------------------------------------------------------------------


def test_program_log_append_notifies_listeners():
    """``append`` / ``clear`` mutate ``entries`` in place (O(1) per line — a
    script may emit thousands) and fire the change listener; consumers mirror
    the log via ``add_change_listener`` rather than value-binding ``entries``."""
    log = ProgramLog()
    calls = 0

    def _on_change() -> None:
        nonlocal calls
        calls += 1

    log.add_change_listener(_on_change)
    log.append(LogEntry(timestamp=time.time(), stream="stdout", text="hi"))
    log.append(LogEntry(timestamp=time.time(), stream="stderr", text="oops"))
    assert [e.text for e in log.entries] == ["hi", "oops"]
    assert calls == 2
    log.clear()
    assert log.entries == []
    assert calls == 3


# ---------------------------------------------------------------------------
# ProgramTabs
# ---------------------------------------------------------------------------


def test_program_tabs_lookup_by_id():
    tabs = ProgramTabs()
    p1 = Program(filename="a.py")
    p2 = Program(filename="b.py")
    tabs.items = [p1, p2]
    assert tabs[p1.id] is p1
    assert tabs[p2.id] is p2
    assert tabs.get(p1.id) is p1
    assert tabs.get("bogus") is None


def test_program_tabs_lookup_raises_on_missing_id():
    tabs = ProgramTabs()
    with pytest.raises(KeyError):
        _ = tabs["nope"]


def test_program_tabs_find_by_path():
    tabs = ProgramTabs()
    p_open = Program(filename="open.py", file_path="/tmp/open.py")
    p_unsaved = Program(filename="new.py")  # file_path=None
    tabs.items = [p_open, p_unsaved]
    assert tabs.find_by_path("/tmp/open.py") is p_open
    assert tabs.find_by_path("/elsewhere.py") is None
    assert tabs.find_by_path(None) is None


def test_program_tabs_active_resolution():
    tabs = ProgramTabs()
    p1 = Program(filename="a.py")
    p2 = Program(filename="b.py")
    tabs.items = [p1, p2]
    tabs.active_id = p2.id
    assert tabs.active is p2
    tabs.active_id = "bogus"
    assert tabs.active is None
