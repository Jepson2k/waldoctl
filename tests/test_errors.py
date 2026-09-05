"""A refusal survives the wire in both directions, and is an exception
a frontend can catch and read."""

import copy
import pickle

import pytest

from waldoctl import RobotError


def test_a_refusal_round_trips_the_wire_and_raises_readably() -> None:
    err = RobotError(7, 42, "Command decode error", "bad frame", "rejected", "resend")
    assert RobotError.from_wire(err.to_wire()).to_wire() == err.to_wire()
    with pytest.raises(RuntimeError) as caught:
        raise err
    assert caught.value is err
    assert caught.value.code == 42 and caught.value.command_index == 7
    assert "Remedy: resend" in str(caught.value)


def test_a_refusal_survives_copy_and_pickle_with_every_field() -> None:
    """A backend snapshots state with deepcopy and a frontend runs scripts
    in a subprocess; both rebuild the exception, and the default rebuild
    for an exception with its own constructor passes only the message."""
    err = RobotError(3, 9, "Not homed", "no reference", "refused", "home first")
    for again in (copy.copy(err), copy.deepcopy(err), pickle.loads(pickle.dumps(err))):
        assert again.to_wire() == err.to_wire()
        assert isinstance(again, RobotError)
