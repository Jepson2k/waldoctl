"""World import/export: one JSON-shaped codec for a ``ShapeWorld``.

Serves both a saved world file and a library entry, because a world *is* its
shapes — a physical object is a ``Shape`` carrying ``physics``, not a separate
kind of record.  Serialization reuses ``Shape.to_wire`` verbatim so there is
exactly one place a shape is turned into data.
"""

from __future__ import annotations

from typing import Any

from waldoctl.shapes import Shape, ShapeWorld, shape_from_wire

SCHEMA = "waldo-world/1"


def world_to_dict(world: ShapeWorld) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "installation": [list(s.to_wire()) for s in world.installation],
        "program": [list(s.to_wire()) for s in world.program],
        "floor_z_m": world.floor_z_m,
    }


def world_from_dict(data: dict[str, Any]) -> ShapeWorld:
    schema = data.get("schema")
    if schema != SCHEMA:
        raise ValueError(f"unsupported world schema {schema!r}; expected {SCHEMA!r}")

    def layer(key: str) -> tuple[Shape, ...]:
        return tuple(shape_from_wire(*entry) for entry in data.get(key, ()))

    floor = data.get("floor_z_m")
    return ShapeWorld(
        installation=layer("installation"),
        program=layer("program"),
        floor_z_m=None if floor is None else float(floor),
    )
