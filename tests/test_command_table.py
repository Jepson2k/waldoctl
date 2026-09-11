"""The command table classifies every ``RobotClient`` method.

Wrappers that swap in for a live client (the stepping wrapper, the path
preview, a backend's dry run) decide what to do with a call from its
``CommandSpec``. A method without one would be stepped, previewed and
waited on by guesswork, so the ABC refuses to grow one.
"""

from __future__ import annotations

import pytest

from waldoctl import CommandKind, RobotClient, command, command_table
from waldoctl.commands import unclassified


def test_every_public_method_of_the_abc_is_classified():
    table = command_table()
    assert len(table) > 40, "introspection stopped finding the ABC's methods"
    assert unclassified(RobotClient) == []
    assert not (set(unclassified(RobotClient)) & set(table))


def test_the_table_carries_what_each_wrapper_needs():
    table = command_table()
    for name, spec in table.items():
        assert spec.name == name
        assert not spec.mints_index or spec.kind in (
            CommandKind.MOTION,
            CommandKind.QUEUED,
        ), f"{name}: only queued work returns an index a program can wait on"
        assert (spec.move_type is not None) == (spec.kind is CommandKind.MOTION), (
            f"{name}: a preview renders motion by its move_type and nothing else"
        )
        assert not spec.cancels or spec.kind is CommandKind.CONTROL
    # The program-facing contract the ABC docstring states, as data.
    assert table["move_j"].move_type == "joints" and table["move_j"].mints_index
    assert table["move_l"].move_type == "cartesian"
    assert table["home"].kind is CommandKind.QUEUED
    assert table["estimate_payload"].kind is CommandKind.MOTION
    assert not table["estimate_payload"].mints_index, "it returns the estimate"
    for streamed in ("servo_j", "servo_l", "jog_j", "jog_l"):
        assert table[streamed].move_type == "jog" and not table[streamed].mints_index, (
            f"{streamed} is fire-and-forget: nothing to wait_command on"
        )
    assert table["stop"].cancels and table["estop"].cancels
    assert table["select_tool"].kind is CommandKind.SYSTEM
    assert table["wait_status"].kind is CommandKind.OBSERVATION
    assert table["io"].kind is CommandKind.OBSERVATION


def test_a_backend_client_keeps_the_abcs_classification_and_can_add_its_own():
    class Backend(RobotClient):
        async def move_j(self, *args, **kwargs):  # override without a marker
            return 0

        @command(CommandKind.SYSTEM)
        async def set_gravity_comp(self, on: bool) -> int:
            return 1

        async def vendor_only(self) -> None:
            return None

    Backend.__abstractmethods__ = frozenset()
    table = command_table(Backend)
    assert table["move_j"].move_type == "joints", (
        "an override inherits the ABC's spec; classification is the contract's"
    )
    assert table["set_gravity_comp"].kind is CommandKind.SYSTEM
    assert unclassified(Backend) == ["vendor_only"]


def test_the_marker_refuses_contradictory_specs():
    with pytest.raises(ValueError, match="move_type"):
        command(CommandKind.QUEUED, move_type="joints")
    with pytest.raises(ValueError, match="move_type"):
        command(CommandKind.MOTION)
    with pytest.raises(ValueError, match="CONTROL"):
        command(CommandKind.SYSTEM, cancels=True)
    with pytest.raises(ValueError, match="index"):
        command(CommandKind.QUERY, mints_index=True)
