"""Camera measurements and validity checks, without capture or robot I/O."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Literal

import numpy as np

from .setup import Parameter, Pose, SetupSnapshot, TcpCalibration


def _numbers(values: Sequence[float], count: int) -> tuple[float, ...]:
    if len(values) != count or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in values
    ):
        raise ValueError(f"Expected {count} finite numbers")
    return tuple(float(v) for v in values)


@dataclass(frozen=True)
class CameraIntrinsics:
    """OpenCV pinhole model: flat row-major K, k1/k2/p1/p2/k3, width/height."""

    camera_matrix: tuple[float, ...]
    dist_coeffs: tuple[float, ...]
    image_size: tuple[int, int]

    def __post_init__(self) -> None:
        k = _numbers(self.camera_matrix, 9)
        if k[0] <= 0 or k[4] <= 0 or (k[1], k[3], *k[6:]) != (0, 0, 0, 0, 1):
            raise ValueError(
                "Camera matrix requires positive focal lengths and canonical pinhole axes"
            )
        if len(self.image_size) != 2 or any(
            type(v) is not int or v <= 0 for v in self.image_size
        ):
            raise ValueError("Image size requires positive integer width and height")
        object.__setattr__(self, "camera_matrix", k)
        object.__setattr__(self, "dist_coeffs", _numbers(self.dist_coeffs, 5))
        object.__setattr__(self, "image_size", tuple(self.image_size))


@dataclass(frozen=True)
class CameraQuality:
    sample_count: int
    method: str
    reproj_rms_px: float
    rot_residual_deg: tuple[float, float]
    trans_residual_mm: tuple[float, float]
    target_spread_mm: float

    def __post_init__(self) -> None:
        if type(self.sample_count) is not int or self.sample_count < 4:
            raise ValueError("Camera calibration requires at least four samples")
        if not isinstance(self.method, str) or not self.method or len(self.method) > 64:
            raise ValueError("Camera calibration requires a solver method")
        residuals = _numbers((self.reproj_rms_px, self.target_spread_mm), 2)
        for name in ("rot_residual_deg", "trans_residual_mm"):
            pair = _numbers(getattr(self, name), 2)
            if pair[0] < 0 or pair[1] < pair[0]:
                raise ValueError("Residuals require 0 <= mean <= maximum")
            object.__setattr__(self, name, pair)
        if min(residuals) < 0:
            raise ValueError("Camera residuals must be nonnegative")


@dataclass(frozen=True)
class CameraCalibration:
    """Camera optical axes (+X right, +Y down, +Z forward), mm and XYZ degrees.

    Tool-mounted ``pose`` is camera→TCP (frame="TCP"). Fixed ``pose`` is
    camera→a static setup frame, whose WRF transform is captured in
    ``reference_wrf``. Device identity must describe the same physical camera,
    lens and capture configuration; remounting or refocusing requires a new
    calibration even when software cannot detect the change.
    """

    camera_id: str
    backend: str
    mount: Literal["tool", "fixed"]
    pose: Pose
    intrinsics: CameraIntrinsics
    quality: CameraQuality
    calibrated_at: str
    board: Mapping[str, bool | int | float | str]
    tool: TcpCalibration | None = None
    reference_wrf: Pose | None = None

    def __post_init__(self) -> None:
        for name in ("camera_id", "backend"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or len(value) > 128:
                raise ValueError(f"{name} requires 1–128 characters")
        if (
            not isinstance(self.pose, Pose)
            or not isinstance(self.intrinsics, CameraIntrinsics)
            or not isinstance(self.quality, CameraQuality)
        ):
            raise ValueError(
                "Camera calibration requires typed pose, intrinsics and quality"
            )
        if not isinstance(self.calibrated_at, str):
            raise ValueError("Calibration time requires an ISO timestamp with timezone")
        when = datetime.fromisoformat(self.calibrated_at.replace("Z", "+00:00"))
        if when.tzinfo is None:
            raise ValueError("Calibration time requires a timezone")
        board = dict(self.board)
        if not board or any(not isinstance(k, str) or not k for k in board):
            raise ValueError("Calibration requires board measurement provenance")
        for value in board.values():
            Parameter(value)
        object.__setattr__(self, "board", MappingProxyType(board))
        if self.mount == "tool":
            if (
                self.pose.frame != "TCP"
                or not isinstance(self.tool, TcpCalibration)
                or self.reference_wrf is not None
            ):
                raise ValueError(
                    "Tool camera requires a TCP-relative pose and tool/TCP binding"
                )
        elif self.mount == "fixed":
            if self.pose.frame == "TCP":
                # Refused here rather than in validate(): TCP is the tool
                # mount's own frame, so a fixed camera naming it is a
                # mismatched calibration, not a missing setup frame.
                raise ValueError(
                    "TCP is the tool-camera pose frame; a fixed camera's pose "
                    "is relative to a static setup frame"
                )
            if (
                self.tool is not None
                or not isinstance(self.reference_wrf, Pose)
                or self.reference_wrf.frame != "WRF"
            ):
                raise ValueError(
                    "Fixed camera requires a WRF reference snapshot and no tool binding"
                )
            if self.pose.frame == "WRF" and not np.allclose(
                self.reference_wrf.matrix(), np.eye(4), atol=1e-8, rtol=0
            ):
                raise ValueError("WRF reference must be the identity")
        else:
            raise ValueError("Camera mount must be tool or fixed")

    def validate(
        self,
        setup: SetupSnapshot,
        *,
        camera_id: str,
        image_size: tuple[int, int],
        backend: str,
        tool: TcpCalibration | None = None,
    ) -> None:
        """Refuse changed acquisition, robot or relevant setup bindings."""
        if camera_id != self.camera_id:
            raise ValueError(
                "Camera source changed; recalibrate or explicitly bind the original camera"
            )
        if tuple(image_size) != self.intrinsics.image_size:
            raise ValueError("Camera resolution changed; recalibrate")
        if backend != self.backend:
            raise ValueError("Robot backend changed; recalibrate")
        if self.mount == "tool":
            expected = self.tool
            assert expected is not None
            if tool is None or (tool.tool_key, tool.variant_key) != (
                expected.tool_key,
                expected.variant_key,
            ):
                raise ValueError("Camera tool or variant changed; recalibrate")
            if not np.allclose(tool.matrix(), expected.matrix(), atol=1e-7, rtol=0):
                raise ValueError("Camera TCP transform changed; recalibrate")
        else:
            assert self.reference_wrf is not None
            if not np.allclose(
                setup.frame_matrix(self.pose.frame),
                self.reference_wrf.matrix(),
                atol=1e-7,
                rtol=0,
            ):
                raise ValueError("Camera reference frame changed; recalibrate")

    def world_pose(
        self,
        setup: SetupSnapshot,
        *,
        camera_id: str,
        image_size: tuple[int, int],
        backend: str,
        tool: TcpCalibration | None = None,
        tcp_pose: Pose | None = None,
    ) -> Pose:
        """Resolve after validation; a tool camera needs the observation's TCP pose."""
        self.validate(
            setup,
            camera_id=camera_id,
            image_size=image_size,
            backend=backend,
            tool=tool,
        )
        if self.mount == "tool":
            if tcp_pose is None or tcp_pose.frame != "WRF":
                raise ValueError("Tool camera requires the observed TCP pose in WRF")
            parent = tcp_pose.matrix()
        else:
            parent = setup.frame_matrix(self.pose.frame)
        return Pose.from_matrix(parent @ self.pose.matrix())

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "backend": self.backend,
            "mount": self.mount,
            "pose": {"values": list(self.pose.values), "frame": self.pose.frame},
            "intrinsics": asdict(self.intrinsics),
            "quality": asdict(self.quality),
            "calibrated_at": self.calibrated_at,
            "board": dict(self.board),
            "tool": self.tool.to_dict() if self.tool else None,
            "reference_wrf": {"values": list(self.reference_wrf.values), "frame": "WRF"}
            if self.reference_wrf
            else None,
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> CameraCalibration:
        data = dict(document)
        try:
            data["pose"] = Pose(**data["pose"])
            data["intrinsics"] = CameraIntrinsics(**data["intrinsics"])
            data["quality"] = CameraQuality(**data["quality"])
            data["tool"] = (
                TcpCalibration(**data["tool"]) if data["tool"] is not None else None
            )
            data["reference_wrf"] = (
                Pose(**data["reference_wrf"])
                if data["reference_wrf"] is not None
                else None
            )
            return cls(**data)
        except (TypeError, KeyError, AttributeError) as error:
            raise ValueError(f"Invalid camera calibration: {error}") from error
