"""Tests for the ``RobotStatus`` surface, its nested bindable sub-objects, and
the ``StatusRate`` a status display picks a broadcast rate from."""

from __future__ import annotations

import time

import pytest
from nicegui import binding

from waldoctl import (
    Action,
    ActionLogEntry,
    AngleArray,
    CartesianJogAvailability,
    ChangeNotifierMixin,
    DriveHealth,
    FrameJogAvailability,
    LinkHealth,
    RobotError,
    RobotStatus,
    StatusRate,
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


# ---------------------------------------------------------------------------
# DriveHealth
# ---------------------------------------------------------------------------


def test_drive_health_reported_covers_every_member():
    """Backends report different subsets, and a supply reading of 0.0 V is a
    report — the drives are down, not unmeasured."""
    assert DriveHealth().reported is False
    assert DriveHealth(temperatures_c=[41.0]).reported is True
    assert DriveHealth(currents_ma=[900.0]).reported is True
    assert DriveHealth(faults=[(), ("overtemperature",)]).reported is True
    assert DriveHealth(bus_voltage_v=0.0).reported is True


# ---------------------------------------------------------------------------
# StatusRate
# ---------------------------------------------------------------------------


def test_achievable_offers_the_whole_number_divisors_of_the_loop():
    """Status goes out every Nth tick, so a 250 Hz loop serves 250/N and a
    100 Hz loop 100/N — a third of the loop rate is never on offer."""
    assert StatusRate(hz=50.0, control_hz=250.0).achievable() == (
        250.0,
        125.0,
        50.0,
        25.0,
        10.0,
        5.0,
        2.0,
        1.0,
    )
    assert StatusRate(hz=50.0, control_hz=100.0).achievable() == (
        100.0,
        50.0,
        25.0,
        20.0,
        10.0,
        5.0,
        4.0,
        2.0,
        1.0,
    )
    assert 100.0 / 3.0 not in StatusRate(hz=50.0, control_hz=100.0).achievable()


def test_the_reported_set_wins_over_the_derived_guess():
    """A controller that says what it accepts is believed, even when the
    derived guess would have offered something else — the guess encodes one
    backend's rule and a backend whose emitter is a wall-clock timer is not
    described by it."""
    reported = StatusRate(hz=30.0, control_hz=250.0, servable=(30.0, 15.0, 7.5))
    assert reported.achievable() == (30.0, 15.0, 7.5)
    assert 125.0 not in reported.achievable()


def test_a_fractional_loop_rate_is_declined_rather_than_rounded():
    """A 62.5 Hz loop rounds to 62 under Python's banker's rule and 63 under
    Rust's — a picker built on either offers rates the other end refuses. So
    the guess declines, and only a controller-reported set answers here."""
    assert StatusRate(hz=1.0, control_hz=62.5).achievable() == ()
    assert StatusRate(hz=1.0, control_hz=1000.0 / 3.0).achievable() == ()
    assert StatusRate(hz=1.0, control_hz=62.5, servable=(62.5, 31.25)).achievable() == (
        62.5,
        31.25,
    )


@pytest.mark.parametrize(
    "control_hz",
    [float("nan"), float("inf"), float("-inf"), 0.0, -100.0],
)
def test_achievable_is_empty_when_the_loop_rate_is_unusable(control_hz):
    """A display renders a rate picker before any status has arrived, or from
    a backend that reports no loop at all; it gets no options, not a crash."""
    assert StatusRate(hz=0.0, control_hz=control_hz).achievable() == ()


@pytest.mark.parametrize(
    ("hz", "control_hz"),
    [
        (50.0, 250.0),
        (50.0, 100.0),
        (20.0, 100.0),
        (100.0, 100.0 + 1e-11),
    ],
)
def test_the_reported_rate_is_one_of_the_achievable_rates(hz, control_hz):
    """The rate a controller is already broadcasting at must survive the
    round trip into a picker, float noise in the loop rate included —
    otherwise the UI shows no current selection."""
    assert hz in StatusRate(hz=hz, control_hz=control_hz).achievable()


# ---------------------------------------------------------------------------
# LinkHealth
# ---------------------------------------------------------------------------


def test_link_health_reported_covers_counters_without_a_state():
    """A backend may report bus counters and no state string. Keying
    availability on ``state`` alone hides that bus completely, which is the
    one case a fieldbus diagnostic exists to show."""
    assert LinkHealth().reported is False
    assert LinkHealth(state="UP").reported is True
    assert LinkHealth(restarts=3).reported is True
    assert LinkHealth(tx_errors=7).reported is True
    assert LinkHealth(rx_frames=1234).reported is True


# ---------------------------------------------------------------------------
# RobotError equality
# ---------------------------------------------------------------------------


def test_two_errors_carrying_the_same_wire_tuple_are_equal():
    """Warnings arrive as a whole list every status tick. Without value
    equality each tick looks like a change, and every bound widget redraws
    at the status rate."""
    wire = [
        -1,
        60,
        "CAN stale",
        "no frames for 200 ms",
        "motion refused",
        "check wiring",
    ]
    assert RobotError.from_wire(wire) == RobotError.from_wire(wire)
    assert [RobotError.from_wire(wire)] == [RobotError.from_wire(wire)]

    other = list(wire)
    other[3] = "no frames for 400 ms"
    assert RobotError.from_wire(wire) != RobotError.from_wire(other)
    assert RobotError.from_wire(wire) != wire


def test_errors_stay_hashable_so_they_can_be_deduped():
    """Defining ``__eq__`` sets ``__hash__`` to None unless it is defined
    too, and an exception that cannot go in a set is a trap for any host
    that dedupes warnings."""
    wire = [-1, 60, "CAN stale", "cause", "effect", "remedy"]
    assert len({RobotError.from_wire(wire), RobotError.from_wire(wire)}) == 1


# ---------------------------------------------------------------------------
# ToolTimeSeries decimation
# ---------------------------------------------------------------------------


def test_pushes_faster_than_the_minimum_interval_are_dropped():
    """A caller pushing at the status rate would fill the window in seconds
    and spend the session evicting samples no chart resolves. Decimating
    keeps the same buffer covering a longer span."""
    series = ToolTimeSeries(max_points=10, min_interval_s=0.05)
    for _ in range(20):
        series.push(1.0, 2.0)
    ts, pos, _cur = series.get_series_if_dirty()
    assert len(ts) == 1, "a burst inside one interval is one sample"
    assert len(pos) == len(ts)

    time.sleep(0.06)
    series.push(3.0, 4.0)
    ts, pos, _cur = series.get_series_if_dirty()
    assert len(ts) == 2
    assert pos[-1] == 3.0


def test_an_undecimated_series_keeps_every_push():
    """The default must stay lossless — decimation is opt-in, so a caller
    that already paces its own pushes is unaffected."""
    series = ToolTimeSeries(max_points=10)
    for i in range(5):
        series.push(float(i), 0.0)
    ts, pos, _cur = series.get_series_if_dirty()
    assert len(ts) == 5
    assert pos == [0.0, 1.0, 2.0, 3.0, 4.0]
