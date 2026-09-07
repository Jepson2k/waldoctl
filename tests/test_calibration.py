import numpy as np
import pytest

from waldoctl.calibration import calibrate_tcp_position, teach_tcp_orientation
from waldoctl.setup import Frame, Parameter, Pose, SetupSnapshot, TcpCalibration


def _pivot_samples():
    tip = np.array([11.0, -7.0, 115.0])
    pivot = np.array([340.0, 80.0, 210.0])
    rotations = [
        np.eye(3),
        np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]]),
        np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]),
        np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]]),
    ]
    samples = []
    for rotation in rotations:
        tool = np.eye(4)
        tool[:3, :3] = rotation
        tool[:3, 3] = pivot - rotation @ tip
        samples.append(Pose.from_matrix(tool))
    return samples, tip, pivot


def test_pivot_calibration_and_separate_orientation_teaching():
    samples, tip, pivot = _pivot_samples()
    result = calibrate_tcp_position(samples, max_error_mm=0.1)
    assert result.offset_mm == pytest.approx(tip)
    assert result.pivot_wrf_mm == pytest.approx(pivot)
    assert result.max_error_mm < 1e-10

    # Re-observing the same pivot far from the origin changes its world
    # coordinates, not the calibrated tip in the registered tool frame.
    shifted = []
    for sample in samples:
        transform = sample.matrix()
        transform[:3, 3] += [1e6, -2e6, 3e6]
        shifted.append(Pose.from_matrix(transform))
    assert calibrate_tcp_position(shifted).offset_mm == pytest.approx(tip)

    axes = Pose((0, 0, 0, 0, 90, 0))
    orientation = teach_tcp_orientation(samples[1], axes)
    calibrated = Pose((*result.offset_mm, *orientation)).matrix()
    achieved = samples[1].matrix() @ calibrated
    assert achieved[:3, 3] == pytest.approx(pivot)
    assert achieved[:3, :3] == pytest.approx(
        np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]), abs=1e-12
    )

    noisy = samples.copy()
    matrix = noisy[-1].matrix()
    matrix[:3, 3] += [0.05, -0.02, 0.03]
    noisy[-1] = Pose.from_matrix(matrix)
    observed = calibrate_tcp_position(noisy, max_error_mm=0.1)
    assert 0 < observed.rms_error_mm <= observed.max_error_mm < 0.1
    assert observed.offset_mm == pytest.approx(tip, abs=0.1)
    with pytest.raises(ValueError, match="disagree"):
        calibrate_tcp_position(noisy, max_error_mm=0.001)

    saved = TcpCalibration(
        (*result.offset_mm, *orientation),
        tool_key="GRIPPER",
        variant_key="probe",
        position_rms_mm=result.rms_error_mm,
        position_samples=result.sample_count,
        orientation_reference="fixture",
    )
    snapshot = SetupSnapshot().with_tcp_calibration("probe", saved)
    document = snapshot.to_dict()
    loaded = SetupSnapshot.from_dict(document)
    document["tcp_calibrations"]["probe"]["values"][2] = 999
    edited = (
        loaded.with_frame("fixture", Frame())
        .with_pose("pick", Pose((1, 2, 3, 0, 0, 0), "fixture"))
        .with_parameter("speed", Parameter(0.2))
    )
    assert samples[1].matrix() @ edited.tcp_calibrations[
        "probe"
    ].matrix() == pytest.approx(achieved)
    assert not edited.without("tcp_calibrations", "probe").tcp_calibrations
    assert loaded.tcp_calibrations["probe"].matrix() == pytest.approx(calibrated)

    for field, value in (
        ("values", [0, 0, float("nan"), 0, 0, 0]),
        ("values", [0, 0, 0]),
        ("position_samples", 3),
        ("position_samples", True),
        ("position_rms_mm", -1),
        ("position_rms_mm", float("inf")),
        ("position_rms_mm", None),
        ("tool_key", ""),
        ("orientation_reference", "../fixture"),
    ):
        invalid = snapshot.to_dict()
        invalid["tcp_calibrations"]["probe"][field] = value
        with pytest.raises(ValueError):
            SetupSnapshot.from_dict(invalid)


def test_pivot_refuses_insufficient_degenerate_or_invalid_observations():
    samples, _, _ = _pivot_samples()
    for count in range(4):
        with pytest.raises(ValueError, match="at least four"):
            calibrate_tcp_position(samples[:count])
    with pytest.raises(ValueError, match="degenerate"):
        calibrate_tcp_position([samples[0]] * 4)
    with pytest.raises(ValueError, match="degenerate"):
        calibrate_tcp_position([Pose((0, 0, 0, 0, 0, yaw)) for yaw in (0, 30, 60, 90)])
    small = [
        Pose((0, 0, 0, r, p, y))
        for r, p, y in ((0, 0, 0), (0.01, 0, 0), (0, 0.01, 0), (0, 0, 0.01))
    ]
    with pytest.raises(ValueError, match="poorly conditioned"):
        calibrate_tcp_position(small)
    for error in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="tolerance"):
            calibrate_tcp_position(samples, max_error_mm=error)
    for condition in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="condition"):
            calibrate_tcp_position(samples, max_condition=condition)
    local = Pose(samples[0].values, frame="fixture")
    with pytest.raises(ValueError, match="WRF"):
        calibrate_tcp_position([local, *samples[1:]])
    for tool, axes in ((local, samples[0]), (samples[0], local)):
        with pytest.raises(ValueError, match="WRF"):
            teach_tcp_orientation(tool, axes)
