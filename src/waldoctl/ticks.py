"""Tick-indexed trajectory records: what a dry run says the arm does.

A dry run has two answers to the same program. The *commanded* record is
the plan — where the controller would tell the arm to go — and it comes
back fast enough to run behind a keystroke. The *predicted* record is the
same commands driven through the backend's own control loop against a
physics plant, which is where servo lag, gravity sag, and a grasp that does
or does not hold live. Both are a :class:`TickIndex`. The host keeps them
side by side because the gap between them, the *following error*, is the
reason to run the second one at all. A backend with no plant answers the
second question with the first record: predicted equals commanded, which
is the honest answer, not a missing one.

These types are storage, not policy. They say what a backend reports and
in what units; how it is drawn is the host's business, and which channels
a backend fills is the backend's.

Debug channels are deliberately untyped. They arrive as a named mapping
of column buffers so a backend can add one (contact forces, centre of
mass, the control loop's own setpoint, whatever a solver exposes) without
a release of this package, and so rendering concerns stay out of a
contracts module.
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
    move_type: str | None = None
    """The path shape a renderer draws for a MOTION command, read from the
    command table (``joints``, ``cartesian``, ``smooth_arc``,
    ``smooth_spline``, ``jog``); None for everything else."""


@dataclass(slots=True)
class TickIndex:
    """One tick-indexed trajectory record, commanded or predicted.

    Sampled columns are ``(rows, ...)`` arrays sharing one row axis, so
    row *r* of every column describes the same instant. ``row_dt_s`` is
    the spacing between rows, which is the resolution of the *record* and
    not of the engine: a backend runs its loop at full rate and keeps only
    what a consumer can display.
    """

    row_dt_s: float
    joints_rad: NDArray[np.float32]
    """``(rows, joints)`` — this record's joint positions: the plan on a
    commanded record, the plant's answer on a predicted one."""
    tcp: NDArray[np.float32]
    """``(rows, 6)`` — this record's TCP ``[x, y, z, rx, ry, rz]``, metres
    and radians."""
    tool_closed: NDArray[np.float32]
    """``(rows,)`` — tool closure, 0 = open … 1 = closed."""
    tool_gripping: NDArray[np.bool_]
    """``(rows,)`` — the tool reports something between its jaws."""
    blocks: tuple[TickBlock, ...] = ()
    objects: tuple[ObjectTicks, ...] = ()
    stop: str = "completed"
    """``"completed"``, ``"failed"`` or ``"budget_exhausted"`` — the last
    meaning the run hit its time limit with work outstanding, so the
    record is real but partial."""
    digest: bytes = b""
    """Identity of the record, over the columns that reach the screen.

    Backends guarantee that the same model, seed and commands produce
    bit-identical output, so an equal digest means an equal picture and a
    host can skip a redraw on it. Empty when the backend does not
    compute one.
    """
    valid: NDArray[np.bool_] | None = None
    """``(rows,)`` — whether each row's pose is one the arm can reach, for
    a planner that keeps going past a failed solve so a preview can show
    how far a line gets. None means every row is valid."""
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
        """Seconds the record covers."""
        return self.rows * self.row_dt_s

    def row_at(self, t_s: float) -> int:
        """The row displayed at time *t_s*, clamped into range."""
        if self.rows == 0:
            return 0
        return max(0, min(self.rows - 1, int(t_s / self.row_dt_s)))

    def block_at(self, row: int) -> TickBlock | None:
        """The command that owns *row*."""
        for b in self.blocks:
            if b.rows and b.start_row <= row < b.start_row + b.rows:
                return b
        return None


def align_rows(source: TickIndex, target: TickIndex) -> NDArray[np.intp]:
    """``(source.rows,)`` — for each row of *source*, the row of *target* to
    compare it with.

    The two records describe one program, but a predicted run spends rows a
    plan does not (settle time after a move, a real homing seek, jaw travel),
    so the same row index is not the same moment. Rows are matched by
    *command*: a source row at offset *k* into command *c*'s block maps to
    offset *k* into *c*'s block in the target, clamped to that block's last
    row. Rows outside any block, and records carrying no blocks, map by
    clamped row index.
    """
    if source.row_dt_s != target.row_dt_s:
        raise ValueError(
            "records sample different tick rates: "
            f"{source.row_dt_s} s/row vs {target.row_dt_s} s/row"
        )
    if target.rows == 0:
        return np.zeros(source.rows, dtype=np.intp)
    out = np.minimum(np.arange(source.rows, dtype=np.intp), target.rows - 1)
    by_command = {b.command: b for b in target.blocks if b.rows}
    for b in source.blocks:
        t = by_command.get(b.command) if b.rows else None
        if t is None:
            continue
        offsets = np.minimum(np.arange(b.rows, dtype=np.intp), t.rows - 1)
        out[b.start_row : b.start_row + b.rows] = t.start_row + offsets
    return out


def following_error(commanded: TickIndex, predicted: TickIndex) -> NDArray[np.float32]:
    """``(predicted.rows,)`` — the worst joint's distance from where it was
    told to be, per predicted row, with the commanded record read at
    :func:`align_rows`. Zero everywhere when the two are the same record.
    This is the quantity a divergence overlay colours by.
    """
    if predicted.rows == 0:
        return np.zeros(0, dtype=np.float32)
    if commanded.rows == 0:
        raise ValueError("the commanded record has no rows to compare against")
    at = align_rows(predicted, commanded)
    gap = np.abs(predicted.joints_rad - commanded.joints_rad[at])
    return gap.max(axis=1).astype(np.float32, copy=False)
