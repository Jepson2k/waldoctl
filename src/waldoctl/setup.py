"""Immutable named setup snapshots; transforms use mm and intrinsic XYZ degrees.

Frames are static parents of other frames or poses. Resolution produces ordinary
WRF numeric poses, so existing client planning, collision checking and stepping
remain responsible for motion. This module performs no storage or robot I/O.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

import numpy as np
from numpy.typing import NDArray

from .signals import DigitalSignal

if TYPE_CHECKING:
    from .camera import CameraCalibration

PoseValues = tuple[float, float, float, float, float, float]
ParameterValue = bool | int | float | str


def validate_name(name: str) -> str:
    """Validate a portable setup/object identifier, also suitable for filenames."""
    if not isinstance(name, str) or not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_-]{0,63}", name
    ):
        raise ValueError(
            "Names must use 1–64 letters, digits, underscores or hyphens, starting with a letter or underscore"
        )
    return name


def _values(values: Sequence[float]) -> PoseValues:
    if len(values) != 6 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in values
    ):
        raise ValueError(
            "A pose requires six finite numbers: x, y, z (mm), roll, pitch, yaw (degrees)"
        )
    return cast(PoseValues, tuple(float(v) for v in values))


def _matrix(values: PoseValues) -> NDArray[np.float64]:
    roll, pitch, yaw = map(math.radians, values[3:])
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    result = np.eye(4)
    result[:3, :3] = rx @ ry @ rz
    result[:3, 3] = values[:3]
    return result


@dataclass(frozen=True)
class Pose:
    values: PoseValues
    frame: str = "WRF"

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", _values(self.values))
        validate_name(self.frame)
        if self.frame == "TRF":
            raise ValueError(
                "Named setup uses static frames; TRF remains a native relative-motion option"
            )

    def as_list(self) -> list[float]:
        return list(self.values)

    def matrix(self) -> NDArray[np.float64]:
        """Return a fresh homogeneous transform, with translation in mm."""
        return _matrix(self.values)

    @classmethod
    def from_matrix(
        cls,
        matrix: Sequence[Sequence[float]] | NDArray[np.float64],
        *,
        frame: str = "WRF",
    ) -> Pose:
        transform = np.asarray(matrix, dtype=float)
        if transform.shape != (4, 4) or not np.isfinite(transform).all():
            raise ValueError("Expected a finite 4×4 rigid transform")
        rotation = transform[:3, :3]
        if (
            not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-8, rtol=0)
            or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-7, rtol=0)
            or not math.isclose(float(np.linalg.det(rotation)), 1.0, abs_tol=1e-7)
        ):
            raise ValueError(
                "Transform must contain a proper rotation and homogeneous last row"
            )
        horizontal = math.hypot(rotation[0, 0], rotation[0, 1])
        pitch = math.atan2(rotation[0, 2], horizontal)
        if horizontal > 1e-9:
            roll = math.atan2(-rotation[1, 2], rotation[2, 2])
            yaw = math.atan2(-rotation[0, 1], rotation[0, 0])
        else:
            roll = math.atan2(rotation[2, 1], rotation[1, 1])
            yaw = 0.0
        return cls(
            cast(
                PoseValues,
                (*map(float, transform[:3, 3]), *map(math.degrees, (roll, pitch, yaw))),
            ),
            frame=frame,
        )


@dataclass(frozen=True)
class Frame:
    values: PoseValues = (0, 0, 0, 0, 0, 0)
    parent: str = "WRF"

    def __post_init__(self) -> None:
        pose = Pose(self.values, self.parent)
        object.__setattr__(self, "values", pose.values)

    def matrix(self) -> NDArray[np.float64]:
        return _matrix(self.values)


@dataclass(frozen=True)
class Parameter:
    value: ParameterValue
    unit: str = ""

    def __post_init__(self) -> None:
        if (
            type(self.value) not in (bool, int, float, str)
            or isinstance(self.value, float)
            and not math.isfinite(self.value)
        ):
            raise ValueError(
                "Parameters must be finite scalar numbers, text or booleans"
            )
        if not isinstance(self.unit, str) or len(self.unit) > 64:
            raise ValueError("Parameter unit must be text of at most 64 characters")


@dataclass(frozen=True)
class TcpCalibration:
    """Explicit user TCP transform and its measured or taught provenance.

    Values use mm and intrinsic XYZ degrees relative to the registered
    tool. An absent position residual or orientation reference means that
    component was entered directly rather than measured or taught.
    """

    values: PoseValues
    tool_key: str
    variant_key: str = ""
    position_rms_mm: float | None = None
    position_samples: int = 0
    orientation_reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", _values(self.values))
        if (
            not isinstance(self.tool_key, str)
            or not self.tool_key
            or len(self.tool_key) > 128
        ):
            raise ValueError("TCP calibration requires a tool key of 1–128 characters")
        if not isinstance(self.variant_key, str) or len(self.variant_key) > 128:
            raise ValueError(
                "TCP calibration variant must be text of at most 128 characters"
            )
        if type(self.position_samples) is not int or (
            self.position_rms_mm is None and self.position_samples != 0
        ):
            raise ValueError("Position sample count requires a measured residual")
        if self.position_rms_mm is not None and (
            isinstance(self.position_rms_mm, bool)
            or not isinstance(self.position_rms_mm, (int, float))
            or not math.isfinite(self.position_rms_mm)
            or self.position_rms_mm < 0
            or self.position_samples < 4
        ):
            raise ValueError(
                "Measured TCP position requires a finite residual and at least four samples"
            )
        if self.orientation_reference is not None:
            validate_name(self.orientation_reference)

    def matrix(self) -> NDArray[np.float64]:
        return _matrix(self.values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "values": list(self.values),
            "tool_key": self.tool_key,
            "variant_key": self.variant_key,
            "position_rms_mm": self.position_rms_mm,
            "position_samples": self.position_samples,
            "orientation_reference": self.orientation_reference,
        }


@dataclass(frozen=True)
class SetupSnapshot:
    frames: Mapping[str, Frame] = field(default_factory=dict)
    poses: Mapping[str, Pose] = field(default_factory=dict)
    parameters: Mapping[str, Parameter] = field(default_factory=dict)
    tcp_calibrations: Mapping[str, TcpCalibration] = field(default_factory=dict)
    signals: Mapping[str, DigitalSignal] = field(default_factory=dict)
    cameras: Mapping[str, CameraCalibration] = field(default_factory=dict)

    def __post_init__(self) -> None:
        from .camera import CameraCalibration

        for label, kind in (
            ("frames", Frame),
            ("poses", Pose),
            ("parameters", Parameter),
            ("tcp_calibrations", TcpCalibration),
            ("signals", DigitalSignal),
            ("cameras", CameraCalibration),
        ):
            entries = dict(getattr(self, label))
            for name, value in entries.items():
                validate_name(name)
                if not isinstance(value, kind):
                    raise ValueError(f"{label}/{name} requires {kind.__name__}")
            object.__setattr__(self, label, MappingProxyType(entries))
        if {"WRF", "TRF", "TCP"} & self.frames.keys():
            # TCP is the tool-camera pose frame: a static frame of that name
            # would silently turn every camera→TCP pose into a world pose
            # resolved through it.
            raise ValueError("WRF, TRF and TCP are reserved frame names")
        for name in self.frames:
            self.frame_matrix(name)
        for pose in self.poses.values():
            self.frame_matrix(pose.frame)

    def frame_matrix(self, name: str = "WRF") -> NDArray[np.float64]:
        result = np.eye(4)
        visited: set[str] = set()
        while name != "WRF":
            if name in visited:
                raise ValueError(f"Frame cycle at {name!r}")
            visited.add(name)
            if name not in self.frames:
                raise ValueError(f"Unknown frame {name!r}")
            frame = self.frames[name]
            result = frame.matrix() @ result
            name = frame.parent
        return result

    def resolve(self, pose: str | Pose) -> Pose:
        """Resolve a named or explicit pose into a numeric WRF snapshot."""
        if isinstance(pose, str):
            if pose not in self.poses:
                # Every missing reference in this module is a ValueError; a
                # caller following that contract would not catch a KeyError,
                # and a bare KeyError names the pose without saying what about
                # it was wrong.
                raise ValueError(f"Unknown pose {pose!r}")
            pose = self.poses[pose]
        return Pose.from_matrix(self.frame_matrix(pose.frame) @ pose.matrix())

    def relative_pose(self, world_pose: Pose, frame: str = "WRF") -> Pose:
        """Express an observed WRF pose in a named frame for teaching."""
        if world_pose.frame != "WRF":
            raise ValueError("Teaching requires an observed WRF pose")
        return Pose.from_matrix(
            np.linalg.inv(self.frame_matrix(frame)) @ world_pose.matrix(), frame=frame
        )

    def with_frame(self, name: str, frame: Frame) -> SetupSnapshot:
        return replace(self, frames={**self.frames, name: frame})

    def with_pose(self, name: str, pose: Pose) -> SetupSnapshot:
        return replace(self, poses={**self.poses, name: pose})

    def with_parameter(self, name: str, parameter: Parameter) -> SetupSnapshot:
        return replace(self, parameters={**self.parameters, name: parameter})

    def with_tcp_calibration(
        self, name: str, calibration: TcpCalibration
    ) -> SetupSnapshot:
        return replace(
            self, tcp_calibrations={**self.tcp_calibrations, name: calibration}
        )

    def with_signal(self, name: str, signal: DigitalSignal) -> SetupSnapshot:
        return replace(self, signals={**self.signals, validate_name(name): signal})

    def with_camera(self, name: str, calibration: CameraCalibration) -> SetupSnapshot:
        return replace(self, cameras={**self.cameras, validate_name(name): calibration})

    def without(self, kind: str, name: str) -> SetupSnapshot:
        if kind not in {
            "frames",
            "poses",
            "parameters",
            "tcp_calibrations",
            "signals",
            "cameras",
        }:
            raise ValueError(
                "Expected frames, poses, parameters, tcp_calibrations, signals or cameras"
            )
        document = self.to_dict()
        del document[kind][name]
        return self.from_dict(document)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "frames": {
                k: {"values": list(v.values), "parent": v.parent}
                for k, v in self.frames.items()
            },
            "poses": {
                k: {"values": list(v.values), "frame": v.frame}
                for k, v in self.poses.items()
            },
            "parameters": {
                k: {"value": v.value, "unit": v.unit}
                for k, v in self.parameters.items()
            },
            "tcp_calibrations": {
                k: v.to_dict() for k, v in self.tcp_calibrations.items()
            },
            "signals": {k: v.to_dict() for k, v in self.signals.items()},
            "cameras": {k: v.to_dict() for k, v in self.cameras.items()},
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> SetupSnapshot:
        """Decode a versioned snapshot, refusing unknown fields or references."""
        from .camera import CameraCalibration

        if (
            not isinstance(document, Mapping)
            or type(document.get("version")) is not int
            or document["version"] != 1
        ):
            raise ValueError("Unsupported setup snapshot version (expected 1)")
        fields = {
            "version",
            "frames",
            "poses",
            "parameters",
            "tcp_calibrations",
            "signals",
            "cameras",
        }
        if set(document) != fields:
            raise ValueError(f"Setup snapshot must contain {', '.join(sorted(fields))}")
        try:
            return cls(
                cameras={
                    k: CameraCalibration.from_dict(v)
                    for k, v in document["cameras"].items()
                },
                signals={k: DigitalSignal(**v) for k, v in document["signals"].items()},
                frames={k: Frame(**v) for k, v in document["frames"].items()},
                poses={k: Pose(**v) for k, v in document["poses"].items()},
                parameters={
                    k: Parameter(**v) for k, v in document["parameters"].items()
                },
                tcp_calibrations={
                    k: TcpCalibration(**v)
                    for k, v in document["tcp_calibrations"].items()
                },
            )
        except (TypeError, AttributeError, KeyError) as error:
            raise ValueError(f"Invalid setup snapshot: {error}") from error
