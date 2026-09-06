"""Tests for ``DryRun``, ``Playback``, and the per-program simulation dataclasses."""

from __future__ import annotations

from nicegui import binding

from waldoctl import (
    DryRun,
    PathSegment,
    Playback,
)


class _Target:
    value: object = None


def test_playback_step_channel_fires_on_executing_step_changes():
    """Running scripts advance executing_step_index; step listeners fan out."""
    pb = Playback()
    step_calls: list[tuple[int, bool]] = []
    pb.add_step_listener(
        lambda: step_calls.append((pb.executing_step_index, pb.executing_step_at_end))
    )
    pb.executing_step_index = 0
    pb.executing_step_at_end = False
    pb.notify_step_changed()
    pb.executing_step_at_end = True
    pb.notify_step_changed()
    assert step_calls == [(0, False), (0, True)]


def test_wholesale_path_segments_reassign_fires_binding():
    dr = DryRun()
    t = _Target()
    binding.bind_from(t, "value", dr, "path_segments", backward=lambda lst: len(lst))
    assert t.value == 0
    dr.path_segments = [
        PathSegment(
            points=[[0, 0, 0], [1, 1, 1]], color="#0f0", is_valid=True, line_number=1
        ),
        PathSegment(
            points=[[1, 1, 1], [2, 2, 2]], color="#00f", is_valid=True, line_number=2
        ),
    ]
    assert t.value == 2
