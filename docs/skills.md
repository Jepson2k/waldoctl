# Python skills

A skill is a typed async function decorated with `waldoctl.skills.skill`.
It receives a client explicitly and composes its operations using ordinary
Python functions, loops and return values. It does not create a connection.

```python
from waldoctl.client import RobotClient
from waldoctl.skills import skill

@skill(id="mybench.read_joints", version="1.0.0")
async def read_joints(rbt: RobotClient) -> list[float] | None:
    return await rbt.angles()

# With a connected synchronous client:
angles = read_joints(rbt)
# With a connected async client, inside an async function:
angles = await read_joints.async_call(async_rbt)
```

Only the first argument changes between the sync and async call surfaces.
Arguments and results keep their annotations. Compose skills with
`await child.async_call(rbt, ...)` inside another skill. Expected outcomes
such as “no object found” should be explicit return values; rejected commands,
unconfirmed completion, disconnection and cancellation must not become success.
Check queued command indices for `>= 0`, and wait for completion when required.
System-command confirmation uses `> 0`, as documented by the client ABC.

Backend sync facades implement `run_skill(invoke)`: invoke receives their async
client, and the facade runs the coroutine on its existing client loop. A wrapper
that intercepts operations must implement this hook with an equivalent async
wrapper. Delegating the underlying client's bound hook bypasses interception.
Async callers supply the wrapped async client directly.

## Capabilities and discovery

`requires=frozenset({"motion.linear"})` rejects an invocation before its body
when the supplied client's `skill_capabilities` lacks that operation. The common
ABC advertises its required joint and linear motion operations. Backends may
extend this set for implemented operations; a capability is not evidence of
current readiness, calibration, or a safety certification. Native command gates
still decide whether each command can execute.

A backend-specific skill can annotate its first argument with that backend's
`AsyncRobotClient` to retain native method completion and type checking. Require
`backend.par6` or `backend.parol6` when using their respective APIs. These
identity capabilities identify the API, not optional hardware or readiness;
additional operations still need their own checks. Shared skills should use
the common `RobotClient` ABC and operation capabilities.

Personal modules work with normal imports. Installed plugins may also register:

```toml
[project.entry-points."waldoctl.skills"]
read_joints = "mybench.skills:read_joints"
```

`discover_skills()` returns decorated callables keyed by stable skill id.
Malformed plugins are logged and skipped; all providers of a duplicate id are
excluded. Metadata versions describe the skill's argument/result semantics.
The plugin is ordinary trusted Python code, not a sandbox.

## Progress and cancellation

Use `report_progress(message, fraction=...)` from a skill. The optional fraction
is between 0 and 1. `with observe_skills(callback): ...` subscribes to started,
progress, completed, failed and cancelled events in that execution context,
including parent/child invocation ids. Observers execute on the client's thread;
GUI consumers must marshal events appropriately. Callback errors are logged and
isolated. Arguments and results are not recorded automatically.

Cancelling an async invocation keeps cancellation sticky at subsequent supplied
client/tool coroutine calls, including nested skills. The runtime requests the
backend's existing stop with a two-second deadline and reports whether it was
confirmed; an unconfirmed stop does not mean the arm stopped. Keep all motion
inside the supplied client and await child work. A saved client guard becomes
unusable after its invocation ends. Python cancellation is cooperative: this
cannot interrupt CPU-bound code, revoke independently created clients, or retain
pose across power loss. There is no automatic retract, rollback or restart.

Planning previews must return command-shaped results. Observation-dependent
branches require explicit fixtures or `UnresolvedPreview`; they must never use
an invented successful sensor handshake.
