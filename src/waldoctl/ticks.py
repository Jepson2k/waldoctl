"""The record of a simulated run: what the arm did, tick by tick.

A dry run has two answers. The first is a *plan* — where the controller
would tell the arm to go — and it comes back fast enough to run behind a
keystroke. The second is a *simulation*: the same commands driven through
the backend's own control loop against a physics plant, which is where
servo lag, gravity sag, and a grasp that does or does not hold live. The
two are stored side by side, because the gap between them is the reason
to run the second one at all.

These types are storage, not policy. They say what a backend reports and
in what units; how it is drawn is the host's business, and which channels
a backend fills is the backend's. A backend that has no physics plant
reports no ticks at all — see ``Robot.has_physics_simulation``.

Debug channels are deliberately untyped. They arrive as a named mapping
of column buffers so a backend can add one (contact forces, centre of
mass, whatever a solver exposes) without a release of this package, and
so rendering concerns stay out of a contracts module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class ObjectTicks:
    """Where one world object went, keyed by its shape name.

    A dynamic object is a ``Shape`` carrying ``physics``, not a separate
    kind of thing, so it has the same identity here as in the collision
    world and in readback. An object that never moved may carry a single
    row, which consumers broadcast; a shape with no free body at all — a
    massless fixture, a keep-out — has no entry.
    """

    name: str
    poses: NDArray[np.float32]
    """``(rows, 7)`` — ``[x, y, z, qw, qx, qy, qz]``, metres."""


@dataclass(frozen=True, slots=True)
class TickBlock:
    """One program command's rows.

    ``rows`` is zero for a command that never ran: one the planner folded
    into a predecessor's blend chain, one refused before it started, or
    one the run stopped short of.
    """

    command: int
    """Index into the program's command list."""
    start_row: int
    rows: int
    line_number: int | None = None
    """Editor line that issued the command, when the host knows it."""
    error: object | None = None
    """The refusal the live controller would answer with, or None."""


@dataclass(slots=True)
class TickIndex:
    """A whole simulated run.

    Sampled columns are ``(rows, ...)`` arrays sharing one row axis, so
    row *r* of every column describes the same instant. ``row_dt_s`` is
    the spacing between rows, which is the resolution of the *record* and
    not of the simulation: a backend runs its control loop at full rate
    and keeps only what a consumer can display.
    """

    row_dt_s: float
    joints_rad: NDArray[np.float32]
    """``(rows, joints)`` — achieved joint positions."""
    commanded_rad: NDArray[np.float32]
    """``(rows, joints)`` — commanded joint positions, post-limiter.

    NaN on rows where nothing was commanded: an idle arm holds itself
    with a torque and no position target, so there is no commanded path
    for the achieved one to diverge from, and a consumer drawing that
    divergence should draw none there rather than invent one.
    """
    tcp: NDArray[np.float32]
    """``(rows, 6)`` — achieved TCP ``[x, y, z, rx, ry, rz]``, metres and
    radians."""
    tool_closed: NDArray[np.float32]
    """``(rows,)`` — tool closure, 0 = open … 1 = closed."""
    tool_gripping: NDArray[np.bool_]
    """``(rows,)`` — the tool reports something between its jaws."""
    blocks: tuple[TickBlock, ...] = ()
    objects: tuple[ObjectTicks, ...] = ()
    stop: str = "completed"
    """``"completed"``, ``"failed"`` or ``"budget_exhausted"`` — the last
    meaning the run hit its simulated-time limit with work outstanding,
    so the record is real but partial."""
    digest: bytes = b""
    """Identity of the run, over the columns that reach the screen.

    Backends guarantee that the same model, seed and commands produce
    bit-identical output, so an equal digest means an equal picture and a
    host can skip a redraw on it. Empty when the backend does not
    compute one.
    """
    channels: dict[str, NDArray] = field(default_factory=dict)
    """Extra named columns for debug overlays, sharing the row axis where
    they are per-row. Ragged channels carry their own offsets under a
    related name; nothing here is required and nothing is interpreted by
    this package."""

    @property
    def rows(self) -> int:
        return int(self.joints_rad.shape[0])

    @property
    def duration_s(self) -> float:
        """Simulated seconds the record covers."""
        return self.rows * self.row_dt_s

    def row_at(self, t_s: float) -> int:
        """The row displayed at simulated time *t_s*, clamped into range."""
        if self.rows == 0:
            return 0
        return max(0, min(self.rows - 1, int(t_s / self.row_dt_s)))

    def block_at(self, row: int) -> TickBlock | None:
        """The command that owns *row*."""
        for b in self.blocks:
            if b.rows and b.start_row <= row < b.start_row + b.rows:
                return b
        return None

    def tracking_error_rad(self) -> NDArray[np.float32]:
        """``(rows,)`` — the worst joint's distance from its command, and
        zero where nothing was commanded. This is the quantity a
        divergence overlay colours by."""
        gap = np.abs(self.joints_rad - self.commanded_rad)
        return np.nan_to_num(gap.max(axis=1), nan=0.0)
