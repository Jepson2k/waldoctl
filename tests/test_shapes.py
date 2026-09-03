"""Shape serialization round-trips through the generic introspective wire form."""

from waldoctl import Box, Capsule, Sphere, shape_from_wire


def test_shape_wire_round_trip_preserves_every_field():
    shapes = [
        Box(name="table", x=0.6, y=0.4, z=0.02, pose=(0.3, 0.0, -0.01, 0, 0, 0)),
        Sphere(name="ball", radius=0.1, collision=False),
        Capsule(name="guard", radius=0.05, length=0.2, margin=0.01),
    ]
    for s in shapes:
        assert shape_from_wire(*s.to_wire()) == s


def test_kind_is_lowercased_classname_and_params_are_in_field_order():
    wire = Box(name="b", x=1.0, y=2.0, z=3.0).to_wire()
    assert wire[0] == "box"
    assert wire[1] == [1.0, 2.0, 3.0]


def test_shape_from_wire_rejects_wrong_param_count():
    """Schema-skewed wire data must raise, not silently build a smaller shape."""
    import pytest

    from waldoctl import shape_from_wire

    with pytest.raises(ValueError, match="takes 1 param"):
        shape_from_wire("sphere", [0.1, 0.2], [0, 0, 0, 0, 0, 0], True, None, "s")
    with pytest.raises(ValueError):
        shape_from_wire("box", [0.1], [0, 0, 0, 0, 0, 0], True, None, "b")


def test_construction_rejects_degenerate_values():
    """Safety geometry must fail loudly at construction: coal accepts NaN or
    non-positive dimensions and then silently never reports a collision — a
    displayed barrier that doesn't exist. Cases from the requirement:
    NaN / inf / negative / zero, bad pose, bad margin."""
    import math

    import pytest

    from waldoctl import Cylinder, Ellipsoid

    nan, inf = math.nan, math.inf
    bad = [
        lambda: Box(name="b", x=nan, y=0.1, z=0.1),
        lambda: Box(name="b", x=inf, y=0.1, z=0.1),
        lambda: Box(name="b", x=-0.1, y=0.1, z=0.1),
        lambda: Sphere(name="s", radius=0.0),
        lambda: Cylinder(name="c", radius=0.05, length=-1.0),
        lambda: Ellipsoid(name="e", radius_x=0.1, radius_y=0.0, radius_z=0.1),
        lambda: Box(name="b", x=0.1, y=0.1, z=0.1, pose=(0, 0, nan, 0, 0, 0)),
        lambda: Box(name="b", x=0.1, y=0.1, z=0.1, pose=(0, 0, 0, 0, 0)),
        lambda: Box(name="b", x=0.1, y=0.1, z=0.1, margin=-0.01),
        lambda: Box(name="b", x=0.1, y=0.1, z=0.1, margin=nan),
    ]
    for ctor in bad:
        with pytest.raises(ValueError):
            ctor()

    # Legitimate non-dimension values stay legal: zero margin, negative
    # pose coordinates.
    Box(name="b", x=0.1, y=0.1, z=0.1, pose=(-1, -1, -1, 0, 0, 0), margin=0.0)
