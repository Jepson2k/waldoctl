"""Workspace keep-out / marker shapes — the collision world.

A shape is a coal collision primitive placed in the world the arm must avoid
(``collision=True``) or a visual-only marker (``collision=False``). Each kind is
a frozen dataclass whose fields ARE the coal constructor params, so the wire and
persisted forms derive from ``dataclasses.fields`` — no per-shape serialize code.
``kind`` is the lowercased class name (``"box"``, ``"sphere"`` …), matching coal's
vocabulary and pinokin's generic ``add_obstacle``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import cast

Pose6 = tuple[float, float, float, float, float, float]

# Fields shared by every shape; everything else on a subclass is a coal param.
_COMMON = ("name", "pose", "collision", "margin")


@dataclass(frozen=True, kw_only=True)
class ShapeBase:
    name: str
    pose: Pose6 = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    """World pose [x, y, z, rx, ry, rz] — metres + radians (RPY)."""
    collision: bool = True
    """In the collision world when True; a visual-only marker when False."""
    margin: float | None = None
    """Per-shape clearance override (metres): collision pairs against this
    shape trigger at this standoff distance.  None → the robot's global
    clearance applies."""

    def __post_init__(self) -> None:
        if len(self.pose) != 6 or not all(math.isfinite(v) for v in self.pose):
            raise ValueError(
                f"{self.kind} {self.name!r}: pose must be 6 finite numbers, "
                f"got {self.pose!r}"
            )
        if self.margin is not None and not (
            math.isfinite(self.margin) and self.margin >= 0
        ):
            raise ValueError(
                f"{self.kind} {self.name!r}: margin must be None or finite >= 0, "
                f"got {self.margin!r}"
            )
        self._validate_params()

    def _validate_params(self) -> None:
        """Default rule: every coal param is a dimension — finite and > 0."""
        for f in fields(self):
            if f.name in _COMMON:
                continue
            v = getattr(self, f.name)
            if not (math.isfinite(v) and v > 0):
                raise ValueError(
                    f"{self.kind} {self.name!r}: {f.name} must be finite and > 0, "
                    f"got {v!r}"
                )

    @property
    def kind(self) -> str:
        return type(self).__name__.lower()

    def params(self) -> list[float]:
        """The coal constructor params, in field order."""
        return [getattr(self, f.name) for f in fields(self) if f.name not in _COMMON]

    def to_wire(self) -> tuple:
        """Generic serialization for the wire and persisted storage."""
        return (
            self.kind,
            self.params(),
            list(self.pose),
            self.collision,
            self.margin,
            self.name,
        )


@dataclass(frozen=True, kw_only=True)
class Box(ShapeBase):
    x: float
    y: float
    z: float
    """Full side lengths (m)."""


@dataclass(frozen=True, kw_only=True)
class Sphere(ShapeBase):
    radius: float


@dataclass(frozen=True, kw_only=True)
class Cylinder(ShapeBase):
    radius: float
    length: float


@dataclass(frozen=True, kw_only=True)
class Capsule(ShapeBase):
    radius: float
    length: float


@dataclass(frozen=True, kw_only=True)
class Cone(ShapeBase):
    radius: float
    length: float


@dataclass(frozen=True, kw_only=True)
class Ellipsoid(ShapeBase):
    radius_x: float
    radius_y: float
    radius_z: float


Shape = Box | Sphere | Cylinder | Capsule | Cone | Ellipsoid

_REGISTRY: dict[str, type[ShapeBase]] = {
    c.__name__.lower(): c for c in (Box, Sphere, Cylinder, Capsule, Cone, Ellipsoid)
}


def shape_from_wire(
    kind: str,
    params: list[float],
    pose: list[float] | Pose6,
    collision: bool = True,
    margin: float | None = None,
    name: str = "",
) -> Shape:
    """Rebuild a ``Shape`` from its ``to_wire`` / persisted form."""
    try:
        cls = _REGISTRY[kind]
    except KeyError:
        raise ValueError(
            f"unknown shape kind {kind!r} — wire/persisted data does not "
            f"match this waldoctl version (known: {', '.join(sorted(_REGISTRY))})"
        ) from None
    pnames = [f.name for f in fields(cls) if f.name not in _COMMON]
    if len(params) != len(pnames):
        raise ValueError(
            f"{kind!r} takes {len(pnames)} param(s), got {len(params)} — "
            "wire/persisted data does not match this waldoctl version"
        )
    obj = cls(
        name=name,
        pose=cast(Pose6, tuple(pose)),
        collision=collision,
        margin=margin,
        **dict(zip(pnames, params)),
    )
    return cast(Shape, obj)


@dataclass(frozen=True)
class ShapeWorld:
    """A backend's applied collision world, split by layer (readback truth).

    ``installation`` comes from the backend's robot config — every program
    inherits it and ``set_shapes`` cannot change it.  ``program`` is the
    last-applied program layer (last-write-wins, persists after program end).
    """

    installation: tuple[Shape, ...] = ()
    program: tuple[Shape, ...] = ()
