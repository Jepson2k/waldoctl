# Static setup snapshots

`waldoctl.setup` supplies immutable `Frame`, `Pose`, `Parameter` and
`SetupSnapshot` values. It has no persistence, robot connection or GUI state.

```python
from waldoctl.setup import Frame, Parameter, Pose, SetupSnapshot

setup = SetupSnapshot(
    frames={"fixture": Frame((100, 200, 0, 0, 0, 90))},
    poses={"pick": Pose((10, 0, 30, 0, 0, 0), frame="fixture")},
    parameters={"clearance": Parameter(30, unit="mm")},
)
target = setup.resolve("pick").as_list()  # WRF [100, 210, 30, 0, 0, 90]
```

All translations are millimetres and rotations are degrees. The rotation
convention is extrinsic XYZ, `Rz(yaw) · Ry(pitch) · Rx(roll)`, matching the
existing robot client pose API. `Pose.matrix()` returns a fresh 4×4 homogeneous
transform with translation in millimetres. `Pose.from_matrix` validates a
proper rigid transform and handles pitch singularities without changing its
orientation.

Frame parents form a static hierarchy rooted at WRF. `resolve` converts a
named or explicit pose to WRF; `relative_pose` converts an observed WRF pose
into a selected frame for teaching. No native frame registry is needed, and
WRF/TRF motion APIs remain unchanged. TRF cannot be a stored static frame.

`with_frame`, `with_pose`, `with_parameter` and `without` return new snapshots.
Editing a frame updates the resolution of every descendant in the new
snapshot. Old snapshots keep their values; dictionaries supplied to a
constructor and exported documents cannot mutate them. Missing references,
frame cycles, non-finite values and removal of a referenced frame are refused.

`to_dict` and `from_dict` provide a versioned JSON-compatible representation.
The host owns storage and loading; Commander exposes these through its Setup
panel and `waldo_commander.setup.load_setup`. Programs pass resolved numeric
poses to their existing clients, preserving native planning and validation.
