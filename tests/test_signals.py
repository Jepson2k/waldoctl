"""Saved channel mappings retain layout and polarity through setup edits."""

import pytest

from waldoctl.setup import Frame, SetupSnapshot, TcpCalibration
from waldoctl.signals import DigitalSignal


def test_named_mappings_preserve_polarity_and_refuse_wrong_channels_or_layouts():
    ready = DigitalSignal("parol6", "input", 1, 2, 2, active_high=False)
    valve = DigitalSignal("parol6", "output", 0, 2, 2)
    setup = SetupSnapshot(
        tcp_calibrations={"tip": TcpCalibration((0, 0, 20, 0, 0, 0), "NONE")}
    )
    setup = setup.with_signal("ready", ready).with_signal("valve", valve)
    restored = SetupSnapshot.from_dict(setup.to_dict()).with_frame("fixture", Frame())
    assert restored.signals["ready"].decode([0, 0, 1, 0, 1])
    assert not restored.signals["ready"].decode([0, 1, 1, 0, 1])
    assert restored.signals["valve"].decode([0, 1, 1, 0, 1])
    assert restored.signals["valve"].encode(False) == 0
    assert restored.tcp_calibrations["tip"].values[2] == 20
    assert "ready" not in restored.without("signals", "ready").signals
    assert "ready" in setup.signals
    for index in (-1, 2, True, 0.5, float("nan")):
        document = setup.to_dict()
        document["signals"]["valve"]["index"] = index
        with pytest.raises(ValueError):
            SetupSnapshot.from_dict(document)
    for levels in (
        [0, 0, 0, 1],
        [0, 0, 0, 0, 0, 1],
        [0, 2, 0, 0, 1],
        [0, float("nan"), 0, 0, 1],
    ):
        with pytest.raises(ValueError):
            ready.decode(levels)
    with pytest.raises(ValueError, match="cannot be written"):
        ready.encode(True)
