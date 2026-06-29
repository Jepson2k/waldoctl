"""Shape serialization round-trips through the generic introspective wire form."""

from waldoctl import Box, Capsule, Plane, Sphere, shape_from_wire


def test_shape_wire_round_trip_preserves_every_field():
    shapes = [
        Box(name="table", x=0.6, y=0.4, z=0.02, pose=(0.3, 0.0, -0.01, 0, 0, 0)),
        Sphere(name="ball", radius=0.1, collision=False),
        Capsule(name="guard", radius=0.05, length=0.2, margin=0.01),
        Plane(name="floor", nx=0.0, ny=0.0, nz=1.0, offset=0.0),
    ]
    for s in shapes:
        assert shape_from_wire(*s.to_wire()) == s


def test_kind_is_lowercased_classname_and_params_are_in_field_order():
    wire = Box(name="b", x=1.0, y=2.0, z=3.0).to_wire()
    assert wire[0] == "box"
    assert wire[1] == [1.0, 2.0, 3.0]
