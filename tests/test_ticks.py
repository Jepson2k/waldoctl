"""Commanded and predicted records compare by command, not by row."""

from __future__ import annotations

import numpy as np

from waldoctl import TickBlock, TickIndex, align_rows, following_error

DT = 0.02
JOINTS = 6


def _record(blocks: list[tuple[int, int]], joints: np.ndarray) -> TickIndex:
    """One record whose blocks tile *joints* rows in order: ``(command, rows)``."""
    spans, start = [], 0
    for command, rows in blocks:
        spans.append(TickBlock(command=command, start_row=start, rows=rows))
        start += rows
    assert start == joints.shape[0]
    rows = joints.shape[0]
    return TickIndex(
        row_dt_s=DT,
        joints_rad=joints.astype(np.float32),
        tcp=np.zeros((rows, 6), dtype=np.float32),
        tool_closed=np.zeros(rows, dtype=np.float32),
        tool_gripping=np.zeros(rows, dtype=np.bool_),
        blocks=tuple(spans),
    )


def _ramp(rows: int, offset: float) -> np.ndarray:
    return offset + np.arange(rows, dtype=np.float64)[:, None] * np.ones(JOINTS)


def test_following_error_is_zero_against_itself():
    commanded = _record([(0, 5), (1, 5)], _ramp(10, 0.0))
    assert not following_error(commanded, commanded).any()


def test_settle_rows_compare_against_the_commanded_block_end_and_later_blocks_realign():
    # Commanded: three commands, five, five and three rows. Predicted: the
    # same, except command 1 takes three extra rows to settle, parked a
    # hair past where it was told to stop.
    commanded = _record([(0, 5), (1, 5), (2, 3)], _ramp(13, 0.0))
    settle_gap = 0.01
    predicted_rows = np.concatenate(
        [
            commanded.joints_rad[0:10],
            np.repeat(commanded.joints_rad[9:10], 3, axis=0) + settle_gap,
            commanded.joints_rad[10:13],
        ]
    )
    predicted = _record([(0, 5), (1, 8), (2, 3)], predicted_rows)

    at = align_rows(predicted, commanded)
    # Command 1's settle rows all read the commanded block's last row.
    assert at[10:13].tolist() == [9, 9, 9]
    # Command 2 realigns row for row despite the three-row offset.
    assert at[13:16].tolist() == [10, 11, 12]

    err = following_error(commanded, predicted)
    assert err.shape == (16,)
    assert not err[0:10].any()
    np.testing.assert_allclose(err[10:13], settle_gap, atol=1e-6)
    assert not err[13:16].any()


def test_records_at_different_tick_rates_are_refused():
    a = _record([(0, 2)], _ramp(2, 0.0))
    b = _record([(0, 2)], _ramp(2, 0.0))
    b.row_dt_s = DT * 2
    try:
        align_rows(a, b)
    except ValueError as e:
        assert "tick rates" in str(e)
    else:
        raise AssertionError("mismatched row_dt_s must not silently mis-align")
