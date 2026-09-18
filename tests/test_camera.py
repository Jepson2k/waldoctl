"""Measured camera poses survive export and reject changed physical bindings."""

from dataclasses import replace
import json

import numpy as np
import pytest

from waldoctl.camera import CameraCalibration, CameraIntrinsics, CameraQuality
from waldoctl.setup import Frame, Parameter, Pose, SetupSnapshot, TcpCalibration


def test_camera_resolution_and_binding_workflow():
    mount = Pose((30, -20, 50, 5, 10, 90), frame="TCP")
    tool = TcpCalibration((1, 2, 3, 4, 5, 6), "MSG", "fingers")
    camera = CameraCalibration(
        "bench-camera",
        "parol6",
        "tool",
        mount,
        CameraIntrinsics(
            (800, 0, 320, 0, 800, 240, 0, 0, 1), (0, 0, 0, 0, 0), (640, 480)
        ),
        CameraQuality(12, "PARK", 0.3, (0.1, 0.3), (0.2, 0.6), 0.4),
        "2026-09-07T10:00:00Z",
        {"square_mm": 30, "dictionary": "DICT_4X4_50"},
        tool=tool,
    )
    setup = SetupSnapshot().with_camera("wrist", camera)
    snapshot = SetupSnapshot.from_dict(json.loads(json.dumps(setup.to_dict())))
    observed = Pose((200, 50, 300, 20, -10, 40))
    context = dict(
        camera_id="bench-camera", image_size=(640, 480), backend="parol6", tool=tool
    )
    resolved = snapshot.cameras["wrist"].world_pose(
        snapshot, **context, tcp_pose=observed
    )
    np.testing.assert_allclose(
        resolved.matrix(), observed.matrix() @ mount.matrix(), atol=1e-8
    )
    for changes, message in (
        ({"camera_id": "other"}, "source"),
        ({"image_size": (1280, 960)}, "resolution"),
        ({"backend": "par6"}, "backend"),
        ({"tool": replace(tool, tool_key="NONE")}, "tool"),
        ({"tool": replace(tool, variant_key="other")}, "variant"),
        ({"tool": replace(tool, values=(1, 2, 3, 4, 5, 7))}, "TCP"),
    ):
        with pytest.raises(ValueError, match=message):
            camera.world_pose(setup, **(context | changes), tcp_pose=observed)
    with pytest.raises(ValueError, match="observed TCP"):
        camera.world_pose(setup, **context)

    # TCP is the tool camera's own frame, so nothing else may claim it: a
    # static frame of that name would turn every camera→TCP pose into a world
    # pose resolved through it, and a fixed camera naming it is a mismatched
    # calibration rather than a missing frame.
    with pytest.raises(ValueError, match="reserved"):
        setup.with_frame("TCP", Frame((1, 2, 3, 0, 0, 0)))
    with pytest.raises(ValueError, match="tool-camera pose frame"):
        replace(
            camera,
            mount="fixed",
            pose=Pose((0, 0, 600, 180, 0, 0), frame="TCP"),
            tool=None,
            reference_wrf=Pose((0, 0, 0, 0, 0, 0)),
        )

    setup = setup.with_frame("table", Frame((100, 0, 50, 0, 0, 30))).with_frame(
        "stand", Frame((0, 100, 0, 0, 0, 0), parent="table")
    )
    fixed = replace(
        camera,
        mount="fixed",
        pose=Pose((0, 0, 600, 180, 0, 0), frame="stand"),
        tool=None,
        reference_wrf=Pose.from_matrix(setup.frame_matrix("stand")),
    )
    setup = setup.with_camera("overhead", fixed)
    expected = setup.frame_matrix("stand") @ fixed.pose.matrix()
    np.testing.assert_allclose(
        fixed.world_pose(setup, **context).matrix(), expected, atol=1e-8
    )
    # Changes unrelated to this camera's reference do not invalidate it.
    changed = setup.with_parameter("count", Parameter(5))
    fixed.validate(changed, **(context | {"tool": None}))
    changed = changed.with_frame("table", Frame((100, 1, 50, 0, 0, 30)))
    with pytest.raises(ValueError, match="reference frame"):
        fixed.world_pose(changed, **context)
    # An existing program's snapshot still resolves the original observation.
    np.testing.assert_allclose(
        fixed.world_pose(setup, **context).matrix(), expected, atol=1e-8
    )
    assert "overhead" not in setup.without("cameras", "overhead").cameras

    for section, field, invalid in (
        ("intrinsics", "camera_matrix", [float("nan")] * 9),
        ("intrinsics", "camera_matrix", [0, 0, 320, 0, 800, 240, 0, 0, 1]),
        ("intrinsics", "image_size", [True, 480]),
        ("intrinsics", "image_size", [-1, 480]),
        ("intrinsics", "dist_coeffs", [0, 0, float("inf"), 0, 0]),
        ("quality", "sample_count", 0),
        ("quality", "reproj_rms_px", -1),
        ("quality", "rot_residual_deg", [1, 0]),
        ("pose", "values", [0, 0, 0, 0, float("nan"), 0]),
    ):
        document = json.loads(json.dumps(setup.to_dict()))
        document["cameras"]["overhead"][section][field] = invalid
        with pytest.raises(ValueError):
            SetupSnapshot.from_dict(document)
