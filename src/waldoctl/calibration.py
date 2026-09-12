"""TCP calibration mathematics, independent of acquisition and robot I/O."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import numpy as np

from .setup import Pose

Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class PivotCalibration:
    """A position-only result; this observation does not determine TCP axes.

    ``offset_mm`` is relative to the registered tool, before any user TCP
    transform. ``pivot_wrf_mm`` is the stationary contact point in WRF.
    """

    offset_mm: Vector3
    pivot_wrf_mm: Vector3
    rms_error_mm: float
    max_error_mm: float
    condition: float
    sample_count: int


def calibrate_tcp_position(
    nominal_tool_poses: Sequence[Pose],
    *,
    max_error_mm: float = 1.0,
    max_condition: float = 1000.0,
) -> PivotCalibration:
    """Fit a fixed tip from at least four diverse orientations at one pivot.

    Each pose describes the registered tool in WRF, with any existing user
    TCP transform removed. Acquisition must hold the same physical tip at
    the same stationary point while changing tool orientation. The caller
    chooses its measurement tolerance; every sample must meet it.

    Reject underdetermined, poorly conditioned, and inconsistent observations.
    This solve never estimates orientation or sends a configuration command.
    """
    if (
        not math.isfinite(max_error_mm)
        or max_error_mm <= 0
        or not math.isfinite(max_condition)
        or max_condition < 1
    ):
        raise ValueError("Require a positive error tolerance and condition limit >= 1")
    if len(nominal_tool_poses) < 4:
        raise ValueError("Pivot calibration requires at least four tool poses")
    if any(pose.frame != "WRF" for pose in nominal_tool_poses):
        raise ValueError("Pivot samples must be registered-tool poses in WRF")

    transforms = np.stack([pose.matrix() for pose in nominal_tool_poses])
    positions = transforms[:, :3, 3]
    origin = positions.mean(axis=0)
    design = np.concatenate(
        [transforms[:, :3, :3], np.broadcast_to(-np.eye(3), (len(transforms), 3, 3))],
        axis=2,
    ).reshape(-1, 6)
    solution, _, rank, singular = np.linalg.lstsq(
        design, -(positions - origin).reshape(-1), rcond=None
    )
    if rank != 6:
        raise ValueError(
            "Pivot samples are degenerate; vary orientation about multiple axes"
        )
    condition = float(singular[0] / singular[-1])
    if condition > max_condition:
        raise ValueError(
            f"Pivot samples are poorly conditioned ({condition:.1f}); use more diverse orientations"
        )
    residuals = (design @ solution + (positions - origin).reshape(-1)).reshape(-1, 3)
    errors = np.linalg.norm(residuals, axis=1)
    maximum = float(errors.max())
    if maximum > max_error_mm:
        raise ValueError(
            f"Pivot samples disagree by {maximum:.3f} mm (limit {max_error_mm:.3f} mm)"
        )
    return PivotCalibration(
        offset_mm=cast(Vector3, tuple(map(float, solution[:3]))),
        pivot_wrf_mm=cast(Vector3, tuple(map(float, solution[3:] + origin))),
        rms_error_mm=float(np.sqrt(np.mean(errors**2))),
        max_error_mm=maximum,
        condition=condition,
        sample_count=len(transforms),
    )


def teach_tcp_orientation(nominal_tool_pose: Pose, reference_axes: Pose) -> Vector3:
    """Align TCP axes with explicit reference axes at the observed tool pose.

    Both poses must be resolved to WRF. Positions do not affect this orientation
    teaching operation. Return intrinsic XYZ degrees relative to the registered
    tool; preserve the separately calibrated translation when applying them.
    """
    if nominal_tool_pose.frame != "WRF" or reference_axes.frame != "WRF":
        raise ValueError("Orientation teaching requires tool and reference axes in WRF")
    local = np.eye(4)
    local[:3, :3] = (
        nominal_tool_pose.matrix()[:3, :3].T @ reference_axes.matrix()[:3, :3]
    )
    return Pose.from_matrix(local).values[3:]
