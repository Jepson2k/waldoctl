"""Tests for ``DryRun``, ``Playback``, and the per-program simulation dataclasses."""

from __future__ import annotations

from nicegui import binding

from waldoctl import (
    DryRun,
    PathSegment,
    Playback,
    ProgramTarget,
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


def test_binding_through_playback_sub_object():
    dr = DryRun()
    t = _Target()
    binding.bind_from(t, "value", dr.playback, "is_playing", backward=lambda v: v)
    dr.playback.is_playing = True
    assert t.value is True


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


def test_program_target_from_dict():
    d = dict(
        id="t0",
        line_number=1,
        pose=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        move_type="cartesian",
        scene_object_id="m0",
    )
    pt = ProgramTarget.from_dict(d)
    assert pt.id == "t0"
    assert pt.line_number == 1
    assert pt.move_type == "cartesian"
    assert pt.is_valid is True


def test_path_segment_from_dict():
    d = dict(
        points=[[0, 0, 0], [1, 1, 1]],
        color="#0f0",
        is_valid=True,
        line_number=2,
        move_type="joints",
    )
    seg = PathSegment.from_dict(d)
    assert seg.points == [[0, 0, 0], [1, 1, 1]]
    assert seg.color == "#0f0"
    assert seg.line_number == 2
    assert seg.move_type == "joints"
    assert seg.is_dashed is True


def test_path_segment_optional_fields_default():
    seg = PathSegment(
        points=[[0, 0, 0], [1, 1, 1]],
        color="#0f0",
        is_valid=True,
        line_number=1,
    )
    assert seg.move_type == "cartesian"
    assert seg.joint_trajectory is None
    assert seg.is_dashed is True
    assert seg.is_travel is False
