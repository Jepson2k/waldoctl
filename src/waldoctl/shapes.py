"""Workspace keep-out / marker shapes — the collision world.

A shape is a coal collision primitive placed in the world the arm must avoid
(``collision=True``) or a visual-only marker (``collision=False``). Each kind is
a frozen dataclass whose fields ARE the coal constructor params, so the wire and
persisted forms derive from ``dataclasses.fields`` — no per-shape serialize code.
``kind`` is the lowercased class name (``"box"``, ``"plane"`` …), matching coal's
vocabulary and pinokin's generic ``add_obstacle``.

A shape may additionally declare ``physics`` (see :class:`Physical`), which is
what promotes it from a purely geometric keep-out to a body the simulator
integrates.  The three levels are derived from what is declared, never named
directly — see :class:`Physical`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import cast

import numpy as np
from numpy.typing import NDArray

Pose6 = tuple[float, float, float, float, float, float]

# Fields shared by every shape; everything else on a subclass is a coal param.
_COMMON = ("name", "pose", "collision", "margin", "physics")


@dataclass(frozen=True, kw_only=True)
class Physical:
    """Physical properties that put a shape into the simulator's world.

    A shape without this is geometry only: it is drawn, and it is a keep-out
    the planner refuses to enter, but nothing can rest on it or push it.
    Declaring it opts the shape into contact:

    ==================  ========================================
    ``mass is None``    static — welded in place, but solid
    ``mass > 0``        dynamic — a free body that falls and is
                        grippable
    ==================  ========================================

    ``mass is None`` is the load-bearing middle case: a table must be a
    keep-out *and* a surface a carried part can be set down on.

    No inertia tensor: it is derived from the geometry and the mass, so a
    caller-supplied tensor could silently disagree with the shape it belongs
    to.  No initial velocity: there is no honest readback for it (echoing the
    spawn value forever is a lie, echoing the live value is not what was set).
    """

    mass: float | None = None
    """Kilograms.  None = static; a positive value = a free body."""
    friction: tuple[float, float, float] = (1.0, 0.005, 0.0001)
    """Sliding, torsional and rolling friction coefficients."""

    def __post_init__(self) -> None:
        if self.mass is not None and not (math.isfinite(self.mass) and self.mass > 0):
            raise ValueError(
                f"physics: mass must be None or finite > 0, got {self.mass!r}"
            )
        if len(self.friction) != 3 or not all(
            math.isfinite(v) and v >= 0 for v in self.friction
        ):
            raise ValueError(
                f"physics: friction must be 3 finite values >= 0, got {self.friction!r}"
            )

    def to_wire(self) -> list:
        return [self.mass, list(self.friction)]

    @classmethod
    def from_wire(cls, w: list | None) -> Physical | None:
        if w is None:
            return None
        mass, friction = w
        return cls(
            mass=mass, friction=cast("tuple[float, float, float]", tuple(friction))
        )


@dataclass(frozen=True, kw_only=True)
class ShapeBase:
    name: str
    pose: Pose6 = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    """World pose [x, y, z, rx, ry, rz] — metres + radians.

    Rotation is **extrinsic XYZ**: ``R = Rz(rz)·Ry(ry)·Rx(rx)``, each angle
    about a fixed world axis.  This is not the intrinsic order some RPY helpers
    use, and the two diverge on any multi-axis tilt.  :func:`pose_matrix` is
    the one implementation; every consumer (collision, physics, rendering)
    must place shapes through it or an equivalent so a keep-out is enforced in
    the orientation it was drawn in."""
    collision: bool = True
    """In the collision world when True; a visual-only marker when False."""
    margin: float | None = None
    """Per-shape clearance override (metres): collision pairs against this
    shape trigger at this standoff distance.  None → the robot's global
    clearance applies."""
    physics: Physical | None = None
    """Opts the shape into the simulator's contact world — see
    :class:`Physical`.  None → geometry and keep-out only."""

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
        if self.physics is not None and not self.collision:
            raise ValueError(
                f"{self.kind} {self.name!r}: collision=False is a visual-only "
                "marker and cannot declare physics — a massed body excluded "
                "from contact would fall through the world forever"
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
        return [getattr(self, p) for p in param_names(type(self))]

    def to_wire(self) -> tuple:
        """Generic serialization for the wire and persisted storage."""
        return (
            self.kind,
            self.params(),
            list(self.pose),
            self.collision,
            self.margin,
            self.name,
            None if self.physics is None else self.physics.to_wire(),
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


@dataclass(frozen=True, kw_only=True)
class Plane(ShapeBase):
    """Half-space barrier (coal Halfspace): solid on the ``n·x <= offset`` side.

    Roughly three orders of magnitude more expensive per collision query than
    every other kind — prefer a large :class:`Box` for floors and walls.  Kept
    for programs that genuinely need an unbounded barrier."""

    nx: float
    ny: float
    nz: float
    offset: float

    def _validate_params(self) -> None:
        """Params are a normal + offset, not dimensions: finite, normal non-zero."""
        for name in ("nx", "ny", "nz", "offset"):
            v = getattr(self, name)
            if not math.isfinite(v):
                raise ValueError(
                    f"plane {self.name!r}: {name} must be finite, got {v!r}"
                )
        if self.nx == 0.0 and self.ny == 0.0 and self.nz == 0.0:
            raise ValueError(f"plane {self.name!r}: normal must be non-zero")


Shape = Box | Sphere | Cylinder | Capsule | Cone | Ellipsoid | Plane

_REGISTRY: dict[str, type[ShapeBase]] = {
    c.__name__.lower(): c
    for c in (Box, Sphere, Cylinder, Capsule, Cone, Ellipsoid, Plane)
}


def param_names(cls: type[ShapeBase]) -> list[str]:
    """The coal constructor parameter names of a shape class, in field
    order — every dataclass field that is a dimension rather than a common
    attribute (name, pose, collision, margin, physics). Editors and code
    emitters enumerate a shape's geometry through this, so a new common
    field cannot masquerade as a dimension anywhere."""
    return [f.name for f in fields(cls) if f.name not in _COMMON]


def shape_from_wire(
    kind: str,
    params: list[float],
    pose: list[float] | Pose6,
    collision: bool = True,
    margin: float | None = None,
    name: str = "",
    physics: list | None = None,
) -> Shape:
    """Rebuild a ``Shape`` from its ``to_wire`` / persisted form."""
    cls = _REGISTRY[kind]
    pnames = param_names(cls)
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
        physics=Physical.from_wire(physics),
        **dict(zip(pnames, params)),
    )
    return cast(Shape, obj)


@dataclass(frozen=True)
class ShapeWorld:
    """A backend's applied collision world, split by layer (readback truth).

    ``installation`` comes from the backend's robot config — every program
    inherits it and ``set_shapes`` cannot change it.  ``program`` is the
    last-applied program layer (last-write-wins, persists after program end).
    ``floor_z_m`` is the installation floor's height, also from the robot
    config: the backend enforces it as a keep-out (reported as
    ``install:floor``) and rests simulated objects on it, and a display
    draws the ground there.  It is not a shape — no program can move it —
    and ``None`` means the backend models no floor.
    """

    installation: tuple[Shape, ...] = ()
    program: tuple[Shape, ...] = ()
    floor_z_m: float | None = None


# ---------------------------------------------------------------------------
# Helpers shared by every consumer of the world: one implementation each.
# ---------------------------------------------------------------------------

INSTALL_PREFIX = "install:"
SHAPE_PREFIX = "shape:"
TOOL_PREFIX = "tool:"


def geom_name(shape: ShapeBase, *, installation: bool = False) -> str:
    """The reporting name of a shape's geometry — the ``install:`` /
    ``shape:`` vocabulary ``StatusBuffer.collision_pairs`` uses, so a pair
    list needs no translation."""
    return f"{INSTALL_PREFIX if installation else SHAPE_PREFIX}{shape.name}"


def display_name(geom: str) -> str:
    """One colliding geometry's reporting name.

    World shapes and tool parts already carry their prefix.  Robot geometry
    drops the per-link index pinocchio appends (``upper_arm_0`` →
    ``upper_arm``) so pairs name URDF links.
    """
    if geom.startswith((INSTALL_PREFIX, SHAPE_PREFIX, TOOL_PREFIX)):
        return geom
    link, sep, index = geom.rpartition("_")
    return link if sep and index.isdigit() else geom


def pose_matrix(pose: Pose6 | list[float]) -> NDArray[np.float64]:
    """A shape ``pose`` as a 4×4 homogeneous transform (column-major).

    ``R = Rz(rz)·Ry(ry)·Rx(rx)`` — extrinsic XYZ; see :attr:`ShapeBase.pose`.
    """
    x, y, z, rx, ry, rz = (float(v) for v in pose)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    T = np.zeros((4, 4), dtype=np.float64, order="F")
    T[:3, :3] = [
        [cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
        [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
        [-sy, cy * sx, cy * cx],
    ]
    T[:3, 3] = (x, y, z)
    T[3, 3] = 1.0
    return T
