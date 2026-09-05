# waldoctl

Shared interface definitions for robot arm control. waldoctl defines the contract between robot arm backends (hardware communication, motion planning) and frontend applications (control interfaces, scripting, visualization).

Named after Robert A. Heinlein's 1942 short story *Waldo*, in which the protagonist invents remote manipulator arms -- the origin of the real-world term "waldo" for teleoperated mechanical hands.

## Installation

```bash
pip install "waldoctl @ git+https://github.com/Jepson2k/waldoctl.git"
```

## Key abstractions

### `Robot`

The single entry point for a backend. One object gives the frontend access to everything: joint configuration (limits, home position), tool definitions, forward/inverse kinematics, URDF paths for 3D rendering, capability flags, and factories for creating clients.

### `RobotClient`

Async control interface spanning motion (`moveJ`, `moveL`, `home`), streaming position targets (`servoJ`, `servoL`), velocity jog (`jogJ`, `jogL`), queries, I/O, and synchronization. Async keeps operations like jogging, status streaming, and motion commands concurrent. For simple automation scripts where `async`/`await` would be unnecessary ceremony, backends also provide a synchronous client.

Core operations are `@abstractmethod`; advanced features like circular moves or freedrive have defaults that raise `NotImplementedError`, so backends only implement what their hardware supports.

### `DryRunClient`

A lightweight shortcut for quick TCP path visualization and basic path verification. Unlike the full simulation mode available on the regular async/sync clients (which ticks the entire controller loop), the dry-run client just runs the motion planner and returns the resulting TCP trajectories and joint paths directly -- fast enough for interactive preview without standing up a full simulated robot.

### World

A `Shape` (`Box`, `Sphere`, `Cylinder`, `Capsule`, `Cone`, `Ellipsoid`, `Plane`) is one thing in the robot's world, in metres and radians. What it *is* follows from what it declares: `collision=False` is a visual marker, a plain shape is a keep-out, and a shape carrying `physics=Physical(...)` is also a body in a backend's contact simulation -- a static fixture without `mass`, a free object with one. `ShapeWorld` is a backend's applied world as read back: the `installation` layer from its robot config, the `program` layer the last `set_shapes` applied, and `floor_z_m`, the installation floor the backend enforces and rests objects on. `waldoctl.world` is the one JSON codec for a saved world, a library object or an import/export document. `ObjectTrack` reports where a physical object went during a previewed program, and `SceneHandle` is a plugin's window into the host's 3D scene, including proposing shapes for the installation layer.

### Tools

A `ToolSpec` describes an end-of-arm tool: TCP offset, 3D mesh descriptors for visualization, motion descriptors (linear jaws, rotary spindles) for animation, UI button configuration, process data channels, and named variants for swapping configurations (e.g. different jaw sets). The typed hierarchy (`ToolSpec` → `GripperTool` → `PneumaticGripperTool` / `ElectricGripperTool`) lets frontends render tool controls and animate tool parts generically without hard-coding knowledge of specific tools.

## Modules

| Module | Contents |
|--------|----------|
| `robot` | `Robot` ABC -- identity, joints, tools, kinematics, lifecycle, client factories |
| `client` | `RobotClient` ABC -- async control interface |
| `dry_run` | `DryRunClient` protocol -- lightweight path preview without full simulation |
| `tools` | Tool hierarchy, mesh/motion descriptors, enums, `ToolStatus` |
| `joints` | Frozen dataclasses for joint configuration and limits |
| `status` | `StatusBuffer` protocol for real-time state, query result types |
| `results` | `IKResult` and `DryRunResult` protocols with concrete dataclasses; `ObjectTrack` |
| `shapes` | `Shape` kinds, `Physical`, `ShapeWorld`, the wire form and the reporting vocabulary |
| `world` | JSON codec for a `ShapeWorld` -- saved worlds, library entries, import/export |
| `scene` | `SceneHandle` protocol -- a plugin's window into the host's 3D scene |
| `dry_run_state` | `PathSegment`, `ToolAction` and the other dry-run records a host keeps |
| `types` | `Frame` and `Axis` type aliases |
| `sync_tools` | Sync wrappers for async tool methods |

For guides on implementing a backend or building scripts, see the [PAROL Web Commander documentation](https://github.com/Jepson2k/PAROL-Web-Commander).

## License

[Apache-2.0](LICENSE)
