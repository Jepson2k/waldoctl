"""Tests for the ``RobotStatus`` surface and its nested bindable sub-objects."""

from __future__ import annotations


import pytest
from nicegui import binding

from waldoctl import (
    Action,
    ActionLogEntry,
    AngleArray,
    CartesianJogAvailability,
    ChangeNotifierMixin,
    FrameJogAvailability,
    RobotStatus,
    ToolTimeSeries,
)


class _Target:
    """Simple object that bindings can write into via ``.value``."""

    value: object = None


def test_action_latest_returns_last_entry():
    a = Action()
    a.history = [
        ActionLogEntry(command_name="first"),
        ActionLogEntry(command_name="second"),
    ]
    assert a.latest is not None
    assert a.latest.command_name == "second"


# ---------------------------------------------------------------------------
# Binding propagation through nested sub-objects
# ---------------------------------------------------------------------------


def test_binding_through_pose():
    s = RobotStatus()
    t = _Target()
    binding.bind_from(t, "value", s.pose, "x", backward=lambda v: v)
    assert t.value == 0.0
    s.pose.x = 42.0
    assert t.value == 42.0


def test_binding_through_tool_status():
    s = RobotStatus()
    t = _Target()
    binding.bind_from(t, "value", s.tool, "key", backward=lambda v: v)
    assert t.value == "NONE"
    s.tool.key = "GRIPPER"
    assert t.value == "GRIPPER"


def test_binding_through_joints_list():
    s = RobotStatus()
    t = _Target()
    binding.bind_from(t, "value", s.joints, "can_jog_pos", backward=tuple)
    # Reassignment fires the binding
    s.joints.can_jog_pos = [False, True, True, True, True, True]
    assert t.value == (False, True, True, True, True, True)


def test_binding_through_io_estop():
    s = RobotStatus()
    t = _Target()
    binding.bind_from(t, "value", s.io, "estop", backward=lambda v: v)
    s.io.estop = 0
    assert t.value == 0


# ---------------------------------------------------------------------------
# In-place mutation vs reassignment
# ---------------------------------------------------------------------------


def test_list_append_does_not_fire_binding():
    """In-place mutation is invisible to ``bindable_dataclass``; this is the
    documented contract that motivates ``ChangeNotifierMixin.notify_changed``.
    """
    a = Action()
    t = _Target()
    binding.bind_from(t, "value", a, "history", backward=lambda h: len(h))
    assert t.value == 0
    a.history.append(ActionLogEntry(command_name="x"))
    # Binding still sees the old length (in-place mutation)
    assert t.value == 0
    # Reassignment does fire it
    a.history = [*a.history, ActionLogEntry(command_name="y")]
    assert t.value == 2


def test_change_listener_fires_on_notify_changed():
    a = Action()
    calls: list[int] = []
    a.add_change_listener(lambda: calls.append(1))
    a.notify_changed()
    a.notify_changed()
    assert calls == [1, 1]


def test_change_listener_removal():
    a = Action()
    calls: list[int] = []

    def cb():
        calls.append(1)

    a.add_change_listener(cb)
    a.notify_changed()
    a.remove_change_listener(cb)
    a.notify_changed()
    assert calls == [1]


def test_change_listener_dedup_on_add():
    a = Action()
    calls: list[int] = []

    def cb():
        calls.append(1)

    a.add_change_listener(cb)
    a.add_change_listener(cb)
    a.notify_changed()
    assert calls == [1]


def test_step_listener_separate_channel():
    """Step listeners fire only on notify_step_changed, not on notify_changed."""
    a = Action()
    change_calls: list[int] = []
    step_calls: list[int] = []
    a.add_change_listener(lambda: change_calls.append(1))
    a.add_step_listener(lambda: step_calls.append(1))
    a.notify_changed()
    assert change_calls == [1]
    assert step_calls == []
    a.notify_step_changed()
    assert change_calls == [1]
    assert step_calls == [1]


def test_step_listener_removal():
    a = Action()
    calls: list[int] = []

    def cb():
        calls.append(1)

    a.add_step_listener(cb)
    a.notify_step_changed()
    a.remove_step_listener(cb)
    a.notify_step_changed()
    assert calls == [1]


def test_remove_listener_works_with_bound_methods():
    """Bound methods compare equal by (instance, func) but fail `is` — the
    remove path uses ``!=`` so bound-method removal works."""

    class Observer:
        def __init__(self):
            self.calls = 0

        def on_change(self):
            self.calls += 1

    a = Action()
    o = Observer()
    a.add_change_listener(o.on_change)
    a.notify_changed()
    a.remove_change_listener(o.on_change)
    a.notify_changed()
    assert o.calls == 1


# ---------------------------------------------------------------------------
# AngleArray
# ---------------------------------------------------------------------------


def test_angle_array_set_deg_updates_both_views():
    import numpy as np

    a = AngleArray(size=3)
    a.set_deg(np.array([90.0, 180.0, 360.0]))
    assert list(a.deg) == [90.0, 180.0, 360.0]
    assert pytest.approx(a.rad[0]) == np.pi / 2
    assert pytest.approx(a.rad[1]) == np.pi


def test_angle_array_set_rad_updates_both_views():
    import numpy as np

    a = AngleArray(size=2)
    a.set_rad(np.array([np.pi, np.pi / 2]))
    assert pytest.approx(a.deg[0]) == 180.0
    assert pytest.approx(a.deg[1]) == 90.0


def test_angle_array_indexing_returns_degrees():
    import numpy as np

    a = AngleArray(size=2)
    a.set_deg(np.array([45.0, 90.0]))
    assert a[0] == 45.0
    assert a[1] == 90.0


# ---------------------------------------------------------------------------
# ToolTimeSeries
# ---------------------------------------------------------------------------


def test_tool_time_series_push_and_dirty_flag():
    s = ToolTimeSeries(max_points=10)
    assert s.get_series_if_dirty() is None  # not dirty yet
    s.push(0.5, 100.0)
    s.push(0.6, 110.0)
    out = s.get_series_if_dirty()
    assert out is not None
    ts, pos, cur = out
    assert pos == [0.5, 0.6]
    assert cur == [100.0, 110.0]
    # Dirty flag cleared
    assert s.get_series_if_dirty() is None


def test_tool_time_series_respects_max_points():
    s = ToolTimeSeries(max_points=3)
    for i in range(5):
        s.push(float(i), float(i * 10))
    out = s.get_series_if_dirty()
    assert out is not None
    _, pos, cur = out
    assert pos == [2.0, 3.0, 4.0]
    assert cur == [20.0, 30.0, 40.0]


def test_tool_time_series_clear():
    s = ToolTimeSeries()
    s.push(0.5, 100.0)
    s.clear()
    assert s.get_series_if_dirty() is None


# ---------------------------------------------------------------------------
# Cartesian jog availability
# ---------------------------------------------------------------------------


def test_cartesian_jog_availability_by_frame():
    c = CartesianJogAvailability()
    assert c.by_frame == {}
    c.by_frame = {"TRF": FrameJogAvailability(), "WRF": FrameJogAvailability()}
    assert "TRF" in c.by_frame
    assert "WRF" in c.by_frame


# ---------------------------------------------------------------------------
# ChangeNotifierMixin reuse on a non-dataclass subclass
# ---------------------------------------------------------------------------


def test_change_notifier_mixin_works_standalone():
    """Verify that ChangeNotifierMixin's lazy listener init works when used
    on a class that isn't a bindable_dataclass."""

    class Plain(ChangeNotifierMixin):
        pass

    p = Plain()
    calls: list[int] = []
    p.add_change_listener(lambda: calls.append(1))
    p.notify_changed()
    assert calls == [1]
