"""Tests for ``Program`` / ``ProgramTabs`` and the program sub-objects."""

from __future__ import annotations

import time

import pytest
from nicegui import binding

from waldoctl import (
    EditFlow,
    EditId,
    LogEntry,
    Program,
    ProgramLog,
    ProgramTabs,
)


class _Target:
    value: object = None


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
# EditFlow
# ---------------------------------------------------------------------------


def _diff_replace_line(line_no_1indexed: int, old: str, new: str) -> str:
    """Build a tiny single-line replacement diff for tests."""
    return f"@@ -{line_no_1indexed},1 +{line_no_1indexed},1 @@\n-{old}\n+{new}\n"


def test_edit_flow_propose_then_approve_mutates_source():
    p = Program(source="a\nb\nc\n")
    edit_id = p.edits.propose(_diff_replace_line(2, "b", "B"), "rename b to B")
    assert len(p.edits.pending) == 1
    pe = p.edits.pending[0]
    assert pe.id == edit_id
    assert pe.description == "rename b to B"
    assert pe.proposed_at > 0
    p.edits.approve(edit_id)
    assert p.source == "a\nB\nc\n"
    assert p.edits.pending == []


def test_edit_flow_propose_then_reject_leaves_source_intact():
    p = Program(source="a\nb\nc\n")
    edit_id = p.edits.propose(_diff_replace_line(2, "b", "B"))
    p.edits.reject(edit_id)
    assert p.source == "a\nb\nc\n"
    assert p.edits.pending == []


def test_edit_flow_drifted_context_raises_value_error_on_approve():
    p = Program(source="a\nb\nc\n")
    edit_id = p.edits.propose(_diff_replace_line(2, "b", "B"))
    p.source = "a\nQ\nc\n"  # human edited under the LLM
    with pytest.raises(ValueError, match="mismatch"):
        p.edits.approve(edit_id)
    # Pending list is untouched on failure so the UI can show "stale" state.
    assert len(p.edits.pending) == 1


def test_edit_flow_unknown_id_raises_key_error():
    p = Program(source="a\nb\nc\n")
    with pytest.raises(KeyError):
        p.edits.approve(EditId("nope"))
    with pytest.raises(KeyError):
        p.edits.reject(EditId("nope"))


def test_edit_flow_double_approve_raises_key_error():
    p = Program(source="a\nb\nc\n")
    edit_id = p.edits.propose(_diff_replace_line(2, "b", "B"))
    p.edits.approve(edit_id)
    with pytest.raises(KeyError):
        p.edits.approve(edit_id)


def test_edit_flow_propose_validates_diff_against_current_source():
    p = Program(source="a\nb\nc\n")
    # context line says "X" but source has "a" — should fail at propose,
    # not silently queue a bad edit.
    with pytest.raises(ValueError, match="mismatch"):
        p.edits.propose("@@ -1,1 +1,1 @@\n-X\n+x\n")
    assert p.edits.pending == []


def test_edit_flow_multi_hunk_apply():
    p = Program(source="a\nb\nc\nd\ne\n")
    diff = "@@ -1,1 +1,1 @@\n-a\n+A\n@@ -4,1 +4,1 @@\n-d\n+D\n"
    edit_id = p.edits.propose(diff)
    p.edits.approve(edit_id)
    assert p.source == "A\nb\nc\nD\ne\n"


def test_edit_flow_insert_into_empty_program():
    # Canonical empty-file insertion hunk @@ -0,0 +1,N @@ (old_start == 0); a
    # new program gets a trailing newline.
    p = Program(source="")
    edit_id = p.edits.propose("@@ -0,0 +1,2 @@\n+import time\n+print(1)\n")
    p.edits.approve(edit_id)
    assert p.source == "import time\nprint(1)\n"


def test_edit_flow_no_final_newline_addition_does_not_concatenate():
    # The last source line has no trailing newline; an addition after it must
    # land on its own line, and no spurious final newline is introduced.
    p = Program(source="print(1)")
    edit_id = p.edits.propose("@@ -1,1 +1,2 @@\n print(1)\n+print(2)\n")
    p.edits.approve(edit_id)
    assert p.source == "print(1)\nprint(2)"


def test_edit_flow_zero_context_insertion_lands_after_old_start():
    # `git diff -U0` for inserting after line 2 emits @@ -2,0 +3 @@ — a pure
    # insertion hunk with no context. It must land AFTER line 2, not before it.
    p = Program(source="a\nb\nc\n")
    edit_id = p.edits.propose("@@ -2,0 +3 @@\n+x\n")
    p.edits.approve(edit_id)
    assert p.source == "a\nb\nx\nc\n"


def test_edit_flow_replacing_last_line_keeps_no_final_newline():
    p = Program(source="a\nb\nc")  # no trailing newline
    edit_id = p.edits.propose("@@ -3,1 +3,1 @@\n-c\n+C\n")
    p.edits.approve(edit_id)
    assert p.source == "a\nb\nC"


def test_edit_flow_preserves_crlf_line_endings():
    p = Program(source="a\r\nb\r\n")
    edit_id = p.edits.propose("@@ -2,1 +2,1 @@\n-b\n+B\n")
    p.edits.approve(edit_id)
    assert p.source == "a\r\nB\r\n"


def test_edit_flow_preserves_exotic_separator_chars_in_untouched_lines():
    # str.splitlines also breaks on \f/\x85/U+2028 etc.; a diff touching an
    # unrelated line must leave a literal containing them byte-identical, not
    # rewrite the separator into \n.
    for sep in ("\f", "\x85", "\u2028"):
        p = Program(source=f'x = 1\ns = "a{sep}b"\n')
        edit_id = p.edits.propose("@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n")
        p.edits.approve(edit_id)
        assert p.source == f'x = 2\ns = "a{sep}b"\n', repr(sep)


def test_edit_flow_tolerates_trailing_blank_line_after_hunk():
    # Hunk extent comes from the @@ header counts; a blank line trailing the
    # diff text must not become phantom empty-context that rejects a clean diff.
    p = Program(source="a\nb\nc\n")
    edit_id = p.edits.propose("@@ -2,1 +2,1 @@\n-b\n+B\n\n")
    p.edits.approve(edit_id)
    assert p.source == "a\nB\nc\n"


def test_edit_flow_blank_context_within_counts_matches_empty_source_line():
    p = Program(source="a\n\nc\n")
    edit_id = p.edits.propose("@@ -1,3 +1,3 @@\n a\n\n-c\n+C\n")
    p.edits.approve(edit_id)
    assert p.source == "a\n\nC\n"


def test_edit_flow_rejects_nonblank_lines_beyond_hunk_counts():
    p = Program(source="a\nb\nc\n")
    with pytest.raises(ValueError):
        p.edits.propose("@@ -2,1 +2,1 @@\n-b\n+B\ngarbage\n")


def test_edit_flow_unbound_raises_runtime_error():
    flow = EditFlow()  # not attached to a Program
    with pytest.raises(RuntimeError, match="not bound"):
        flow.propose("@@ -0,0 +1,1 @@\n+x\n")
    with pytest.raises(RuntimeError, match="not bound"):
        flow.approve(EditId("nope"))


def test_edit_flow_pending_reassignment_fires_binding():
    """``pending`` is reassigned wholesale on propose/approve/reject so
    bindings to ``EditFlow.pending`` fire on each change."""
    p = Program(source="a\nb\nc\n")
    t = _Target()
    binding.bind_from(t, "value", p.edits, "pending", backward=lambda lst: len(lst))
    edit_id = p.edits.propose(_diff_replace_line(2, "b", "B"))
    assert t.value == 1
    p.edits.approve(edit_id)
    assert t.value == 0


def test_edit_flow_notify_changed_fires_on_lifecycle():
    """``EditFlow`` fires its ChangeNotifierMixin channel on every
    propose/approve/reject so the WC editor's diff-overlay refresher
    re-renders without needing per-field bindings."""
    p = Program(source="a\nb\nc\n")
    calls: list[str] = []
    p.edits.add_change_listener(lambda: calls.append("x"))
    edit_id = p.edits.propose(_diff_replace_line(2, "b", "B"))
    assert calls == ["x"]
    p.edits.reject(edit_id)
    assert calls == ["x", "x"]
    # Approve also fires (via the propose+approve roundtrip).
    edit_id2 = p.edits.propose(_diff_replace_line(2, "b", "B"))
    p.edits.approve(edit_id2)
    assert calls == ["x", "x", "x", "x"]


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
