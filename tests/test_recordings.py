"""Demonstrations keep their observations' order and refuse to bridge gaps."""

import pytest

from waldoctl.recordings import Demonstration, RecordedSample


def _sample(
    seq: int, observed_ns: int, received_ns: int | None = None
) -> RecordedSample:
    received = observed_ns + 5_000 if received_ns is None else received_ns
    return RecordedSample(seq, observed_ns, received, (1.0, 2.0, 3.0, 4.0, 5.0, 6.0))


def _recording(samples: tuple[RecordedSample, ...]) -> Demonstration:
    return Demonstration(
        backend="parol6",
        session_id=7,
        simulator=True,
        tcp_transform=(0, 0, 0, 0, 0, 0),
        requested_rate_hz=50.0,
        gap_threshold_s=0.05,
        ended="stopped",
        samples=samples,
    )


def test_a_recording_tolerates_a_coarse_host_clock_but_not_reordered_observations():
    # Two publications 20 ms apart landed on the same host clock tick.
    shared = _recording(
        (
            _sample(1, 0, received_ns=100),
            _sample(2, 20_000_000, received_ns=100),
            _sample(3, 40_000_000, received_ns=200),
        )
    )
    assert shared.gaps == ()
    assert shared.duration_s == pytest.approx(0.04)
    assert shared.observed_rate_hz == pytest.approx(50.0)
    shared.require_continuous()
    for reordered in (
        (_sample(1, 0), _sample(2, 0)),
        (_sample(2, 0), _sample(1, 20_000_000)),
        (_sample(1, 0, received_ns=200), _sample(2, 20_000_000, received_ns=100)),
    ):
        with pytest.raises(ValueError, match="order"):
            _recording(reordered)

    # A dropped publication and a late one are both gaps a replay may not bridge.
    gapped = _recording(
        (
            _sample(1, 0),
            _sample(2, 20_000_000),
            _sample(4, 40_000_000),
            _sample(5, 160_000_000),
            _sample(6, 180_000_000),
        )
    )
    assert [(g.sample_index, g.missing_publications) for g in gapped.gaps] == [
        (2, 1),
        (3, 0),
    ]
    assert gapped.gaps[1].elapsed_s == pytest.approx(0.12)
    with pytest.raises(ValueError, match="uninterrupted"):
        gapped.require_continuous()
    clean = gapped.select(3, 5)
    assert clean.samples[0].observed_ns == 160_000_000 and clean.session_id == 7
    assert clean.gaps == ()
    clean.require_continuous()
    with pytest.raises(ValueError, match="at least two"):
        gapped.select(0, 1).require_continuous()
    with pytest.raises(ValueError, match="nonempty"):
        gapped.select(3, 3)
