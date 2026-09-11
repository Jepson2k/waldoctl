"""Static frame composition and reusable snapshots, independent of a backend."""

from types import MappingProxyType

import numpy as np
import pytest

from waldoctl.setup import Frame, Parameter, Pose, SetupSnapshot


def test_fixture_update_moves_shared_poses_without_mutating_loaded_values():
    frames = {"fixture": Frame((100, 200, 300, 0, 0, 90))}
    setup = SetupSnapshot(frames=frames).with_frame(
        "tray", Frame((10, 0, 0, 0, 0, 90), "fixture")
    )
    setup = setup.with_pose("pick", Pose((2, 3, 4, 0, 0, 0), "tray"))
    setup = setup.with_pose("approach", Pose((2, 3, 14, 0, 0, 0), "tray"))
    setup = setup.with_parameter("speed", Parameter(0.2))
    assert setup.resolve("pick").values[:3] == pytest.approx((98, 207, 304))
    assert setup.resolve("approach").values[:3] == pytest.approx((98, 207, 314))
    assert setup.resolve("pick").matrix()[:3, :3] == pytest.approx(np.diag([-1, -1, 1]))
    taught = setup.relative_pose(setup.resolve("pick"), "tray")
    assert taught.values == pytest.approx(setup.poses["pick"].values)

    moved = setup.with_frame("fixture", Frame((150, 200, 300, 0, 0, 90)))
    for name in ("pick", "approach"):
        assert np.array(moved.resolve(name).values[:3]) - setup.resolve(name).values[
            :3
        ] == pytest.approx((50, 0, 0))
    frames["fixture"] = Frame()
    assert setup.resolve("pick").values[:3] == pytest.approx((98, 207, 304))
    encoded = moved.to_dict()
    restored = SetupSnapshot.from_dict(encoded)
    encoded["frames"]["fixture"]["values"][0] = -1000
    assert restored.resolve("pick").values == pytest.approx(
        moved.resolve("pick").values
    )

    turned = SetupSnapshot(
        frames={"fixture": Frame((100, 200, 300, 90, 0, 90))},
        poses={"pick": Pose((10, 0, 0, 0, 0, 0), "fixture")},
    )
    # Native robot poses rotate about successive axes: Rx(90) @ Rz(90)
    # sends fixture X along world Z, unlike the shape-pose convention.
    assert turned.resolve("pick").values[:3] == pytest.approx((100, 200, 310))
    assert turned.relative_pose(turned.resolve("pick"), "fixture").values[
        :3
    ] == pytest.approx((10, 0, 0))

    for pitch in (-90, -89.99, 25, 89.99, 90):
        original = Pose((1, 2, 3, 37, pitch, -28))
        assert Pose.from_matrix(original.matrix()).matrix() == pytest.approx(
            original.matrix()
        )


def test_invalid_setup_never_resolves_into_a_motion_target():
    setup = SetupSnapshot(
        frames={"fixture": Frame()}, poses={"pick": Pose((1, 2, 3, 0, 0, 0), "fixture")}
    )
    with pytest.raises(ValueError, match="Unknown frame"):
        setup.without("frames", "fixture")
    with pytest.raises(ValueError, match="cycle"):
        setup.with_frame("fixture", Frame(parent="fixture"))
    with pytest.raises(ValueError, match="Unknown frame"):
        setup.with_frame("fixture", Frame(parent="missing"))
    with pytest.raises(ValueError, match="cycle"):
        SetupSnapshot(frames={"a": Frame(parent="b"), "b": Frame(parent="a")})
    for value in (float("nan"), float("inf"), float("-inf")):
        document = setup.to_dict()
        document["poses"]["pick"]["values"][0] = value
        with pytest.raises(ValueError, match="finite"):
            SetupSnapshot.from_dict(document)
        document = setup.to_dict()
        document["parameters"]["speed"] = {"value": value}
        with pytest.raises(ValueError, match="finite"):
            SetupSnapshot.from_dict(document)
    for transform in (np.diag([1, 1, -1, 1]), np.diag([2, 1, 1, 1]), np.zeros((4, 4))):
        with pytest.raises(ValueError, match="proper rotation"):
            Pose.from_matrix(transform)
    document = setup.to_dict()
    document["version"] = 2
    with pytest.raises(ValueError, match="version"):
        SetupSnapshot.from_dict(document)
    # A mistyped pose name is a missing reference like any other, so a caller
    # catching ValueError catches it.
    with pytest.raises(ValueError, match="Unknown pose 'pikc'"):
        setup.resolve("pikc")
    # Any mapping decodes: a read-only view of a valid document is not an
    # unsupported version.
    assert SetupSnapshot.from_dict(MappingProxyType(setup.to_dict())).resolve(
        "pick"
    ).values == pytest.approx(setup.resolve("pick").values)
