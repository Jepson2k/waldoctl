"""Open programs — source, dry-run preview, log, execution, recording, edits.

``ProgramTabs`` is the container; ``Program`` is one open file with its own
sub-objects. Multiple programs can be open at once; one is active at a time.

**Mutate-in-place invariant**: ``program.execution``, ``program.recording``,
``program.edits``, ``program.log``, and ``program.dry_run`` are constructed
once with the Program and never swapped.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from nicegui import binding

from waldoctl.dry_run_state import DryRun
from waldoctl.notify import ChangeNotifierMixin


# ---------------------------------------------------------------------------
# ProgramLog — per-program stdout / stderr capture
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LogEntry:
    """One line of captured output from a program's script execution."""

    timestamp: float
    stream: str  # "stdout" or "stderr"
    text: str


@binding.bindable_dataclass
class ProgramLog(ChangeNotifierMixin):
    """Per-program execution output.

    Entries are appended by the host application's script runner as the
    program emits stdout / stderr — potentially thousands of lines per run.
    ``append`` / ``clear`` mutate ``entries`` in place and call
    :meth:`notify_changed`, so each line is O(1); consumers that mirror the
    log subscribe via ``add_change_listener`` (like
    ``commander.status.action.history``) rather than value-binding ``entries``.
    """

    entries: list[LogEntry] = field(default_factory=list)

    def append(self, entry: LogEntry) -> None:
        """Add a log entry and notify listeners."""
        self.entries.append(entry)
        self.notify_changed()

    def clear(self) -> None:
        """Drop all captured output and notify listeners."""
        self.entries.clear()
        self.notify_changed()


# ---------------------------------------------------------------------------
# Execution — script lifecycle on one program
# ---------------------------------------------------------------------------


@binding.bindable_dataclass
class Execution(ChangeNotifierMixin):
    """Script execution lifecycle for one ``Program``.

    The asyncio process handle that backs script execution stays in the host
    application (one program runs at a time, enforced there); this surface
    exposes the bindable ``is_running`` flag. The ``run`` / ``stop`` / ``pause``
    / ``resume`` methods are stubs that ``raise NotImplementedError`` until the
    host wires them.
    """

    is_running: bool = False

    def run(self) -> None:
        """Start this program. Raises if any program in the session is
        already running (the host application enforces this invariant)."""
        raise NotImplementedError("host application wires execution.run")

    def stop(self) -> None:
        """Stop this program. No-op if not running."""
        raise NotImplementedError("host application wires execution.stop")

    def pause(self) -> None:
        """Pause this program. Requires is_running."""
        raise NotImplementedError("host application wires execution.pause")

    def resume(self) -> None:
        """Resume from pause. Requires the program to be paused."""
        raise NotImplementedError("host application wires execution.resume")


# ---------------------------------------------------------------------------
# Recording — motion-recording lifecycle on one program
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RecordedProgram:
    """Snapshot returned by :meth:`Recording.stop` describing the captured code."""

    source: str
    """Generated program text (typically Python with ``rbt.move_l(...)`` etc.)."""
    started_at: float
    stopped_at: float


@binding.bindable_dataclass
class Recording(ChangeNotifierMixin):
    """Motion recording lifecycle for one ``Program``.

    The host application's ``motion_recorder`` service enforces the
    one-recording-at-a-time invariant across all programs and routes captured
    code into the program that started the recording. This surface exposes the
    bindable ``is_recording`` flag; the ``start`` / ``stop`` methods are stubs
    that ``raise NotImplementedError`` until the host wires them.
    """

    is_recording: bool = False

    def start(self) -> None:
        """Begin recording into this program. Raises if any other program is
        currently recording."""
        raise NotImplementedError("host application wires recording.start")

    def stop(self) -> RecordedProgram:
        """Stop recording and return the captured program."""
        raise NotImplementedError("host application wires recording.stop")

    def discard(self) -> None:
        """Stop recording and drop the captured code."""
        raise NotImplementedError("host application wires recording.discard")


# ---------------------------------------------------------------------------
# EditFlow — proposed-edit lifecycle (Claude-Code style, edit-level)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EditId:
    """Opaque identifier for a proposed edit."""

    value: str


@dataclass(frozen=True, slots=True)
class PendingEdit:
    """A proposed change to a program's source, awaiting approve/reject."""

    id: EditId
    diff: str  # Unified-diff text
    proposed_at: float
    description: str = ""


@binding.bindable_dataclass
class EditFlow(ChangeNotifierMixin):
    """Claude-Code-style proposed-edits lifecycle.

    Plugins / LLMs / MCP tools propose edits as unified-diff text; the
    frontend renders pending edits and the user approves or rejects each one
    as a whole. Real implementation ships in stack PR 4 (CodeMirror diff
    overlay + apply logic).
    """

    pending: list[PendingEdit] = field(default_factory=list)

    def propose(self, diff: str, description: str = "") -> EditId:
        """Submit a proposed edit; returns its assigned id."""
        raise NotImplementedError("ships in PR 4")

    def approve(self, edit_id: EditId) -> None:
        """Apply the edit's diff to the program's source."""
        raise NotImplementedError("ships in PR 4")

    def reject(self, edit_id: EditId) -> None:
        """Discard the edit without applying."""
        raise NotImplementedError("ships in PR 4")


# ---------------------------------------------------------------------------
# Program — one open program
# ---------------------------------------------------------------------------


def _new_program_id() -> str:
    return uuid.uuid4().hex


@binding.bindable_dataclass
class Program(ChangeNotifierMixin):
    """A single open program: source plus sub-objects for dry-run, log,
    execution, recording, and edits.

    File-level identity (``id``, ``filename``, ``file_path``, ``created_at``)
    lives at the top. ``source`` is the live editor content; ``_saved_source``
    is the snapshot at last save and drives :prop:`is_dirty`.

    **Mutate-in-place invariant**: ``dry_run``, ``log``, ``execution``,
    ``recording``, ``edits`` are constructed once with the Program and never
    reassigned.
    """

    id: str = field(default_factory=_new_program_id)
    filename: str = "untitled.py"
    file_path: str | None = None
    created_at: float = field(default_factory=time.time)
    source: str = ""
    _saved_source: str = ""
    dry_run: DryRun = field(default_factory=DryRun)
    log: ProgramLog = field(default_factory=ProgramLog)
    execution: Execution = field(default_factory=Execution)
    recording: Recording = field(default_factory=Recording)
    edits: EditFlow = field(default_factory=EditFlow)

    @property
    def is_dirty(self) -> bool:
        """True if the editor source has changed since last save."""
        return self.source != self._saved_source

    def mark_saved(self) -> None:
        """Snapshot the current source as saved; clears the dirty flag.

        Host-application save flows call this after a successful disk write.
        """
        self._saved_source = self.source

    # File operations live at the program level — they're whole-file actions.
    def save(self, path: str | None = None) -> None:
        """Persist ``source`` to disk (uses ``file_path`` if ``path`` is None)."""
        raise NotImplementedError("host application wires program.save")

    def reload(self) -> None:
        """Reload ``source`` from ``file_path``, discarding unsaved edits."""
        raise NotImplementedError("host application wires program.reload")


# ---------------------------------------------------------------------------
# ProgramTabs — the open-programs container
# ---------------------------------------------------------------------------


@binding.bindable_dataclass
class ProgramTabs(ChangeNotifierMixin):
    """Container for the open programs. One is active at a time.

    Lookups by id use ``programs[id]`` (raises ``KeyError``) or
    ``programs.get(id)`` (returns ``None``). Path is the natural outside key
    for MCP / file-operation tools — use :meth:`find_by_path`.

    **List-reassign invariant**: the ``items`` list is reassigned wholesale
    on open / close so bindings fire (the opposite of the sub-object
    "mutate-in-place" rule elsewhere); individual ``Program`` instances are
    long-lived and their sub-objects must not be reassigned.
    """

    items: list[Program] = field(default_factory=list)
    active_id: str | None = None

    @property
    def active(self) -> Program | None:
        """The currently active program, or ``None`` if no programs are open."""
        return self.get(self.active_id) if self.active_id else None

    # --- Actions ----------------------------------------------------------
    def open(self, path: str) -> Program:
        """Load ``path`` from disk into a new ``Program`` (or focus the existing
        one if a program with this path is already open)."""
        raise NotImplementedError("host application wires programs.open")

    def new(
        self,
        source: str = "",
        filename: str = "untitled.py",
        file_path: str | None = None,
    ) -> Program:
        """Create a fresh program with the given starter source.

        ``filename`` is the display name. ``file_path`` is the on-disk path if
        the new program represents an existing file being opened; ``None`` for
        a pristine unsaved program.
        """
        raise NotImplementedError("host application wires programs.new")

    def close(self, id: str) -> None:
        """Close the program with the given id."""
        raise NotImplementedError("host application wires programs.close")

    def switch(self, id: str) -> None:
        """Make the program with the given id active."""
        raise NotImplementedError("host application wires programs.switch")

    # --- Lookups ----------------------------------------------------------
    def __getitem__(self, id: str) -> Program:
        for p in self.items:
            if p.id == id:
                return p
        raise KeyError(id)

    def get(self, id: str) -> Program | None:
        for p in self.items:
            if p.id == id:
                return p
        return None

    def find_by_path(self, path: str | None) -> Program | None:
        """Return the program with matching ``file_path`` (``None`` if no
        match, or if ``path`` itself is ``None``)."""
        if path is None:
            return None
        for p in self.items:
            if p.file_path == path:
                return p
        return None
