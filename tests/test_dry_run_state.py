"""Tests for ``DryRun``, ``Playback``, and the per-program simulation dataclasses."""

from __future__ import annotations

from nicegui import binding

from waldoctl import (
    DryRun,
    PathSegment,
    Playback,
    ProgramTarget,
    ToolAction,
    ToolSelection,
)


class _Target:
    value: object = None


def test_dry_run_defaults_are_empty():
    dr = DryRun()
    assert dr.targets == []
    assert dr.path_segments == []
    assert dr.tool_actions == []
    assert dr.tool_selections == []
    assert dr.total_steps == 0
    assert dr.total_duration == 0.0
    assert dr.final_joints_rad is None
    assert dr.last_sim_joints_deg is None
    assert dr.paths_visible is True
    assert isinstance(dr.playback, Playback)


def test_playback_defaults():
    pb = Playback()
    assert pb.is_playing is False
    assert pb.is_active is False
    assert pb.current_step == 0
    assert pb.playback_time == 0.0
    assert pb.playback_speed == 1.0
    assert pb.active_cursor_line == 0


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


def test_program_target_from_dict_roundtrip():
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


def test_tool_action_construction():
    ta = ToolAction(
        tcp_pose=None,
        motions=[],
        target_positions=(0.5,),
        activation_type="binary",
        line_number=1,
        method="close",
    )
    assert ta.method == "close"
    assert ta.segment_index == -1
    assert ta.estimated_duration == 0.0


def test_tool_selection_defaults():
    ts = ToolSelection(tool_key="GRIPPER")
    assert ts.tool_key == "GRIPPER"
    assert ts.variant_key == ""
    assert ts.segment_index == -1
    assert ts.line_number == 0
