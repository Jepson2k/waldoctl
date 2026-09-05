"""Client-side exception for runtime-reported errors (the wire 6-tuple)."""

from __future__ import annotations

from collections.abc import Sequence


class RobotError(RuntimeError):
    """A KUKA-style error reported by the runtime.

    Carries the wire error tuple ``[command_index, code, title, cause,
    effect, remedy]``.  ``command_index`` is the queued command the error is
    attributed to (``-1`` = unattributable).
    """

    def __init__(
        self,
        command_index: int,
        code: int,
        title: str,
        cause: str,
        effect: str,
        remedy: str,
    ) -> None:
        self.command_index = command_index
        self.code = code
        self.title = title
        self.cause = cause
        self.effect = effect
        self.remedy = remedy
        super().__init__(f"[{code}] {title}")

    def __reduce__(self) -> tuple:
        # An exception with its own constructor reduces, by default, to
        # ``(cls, self.args)`` — the one formatted message — so a copy or
        # a pickle (a state snapshot, a script subprocess) rebuilt it with
        # five fields missing. Rebuild from the six fields instead.
        return (
            type(self),
            (
                self.command_index,
                self.code,
                self.title,
                self.cause,
                self.effect,
                self.remedy,
            ),
        )

    def to_wire(self) -> list:
        """The wire 6-tuple, the inverse of :meth:`from_wire` — what a
        backend's server puts in an ERROR message."""
        return [
            self.command_index,
            self.code,
            self.title,
            self.cause,
            self.effect,
            self.remedy,
        ]

    @classmethod
    def from_wire(cls, err: Sequence) -> "RobotError":
        """Build from the wire 6-tuple ``[index, code, title, cause, effect, remedy]``."""
        index, code, title, cause, effect, remedy = err
        return cls(index, code, title, cause, effect, remedy)

    def __str__(self) -> str:
        return (
            f"[{self.code}] {self.title}\n"
            f"  Cause:  {self.cause}\n"
            f"  Effect: {self.effect}\n"
            f"  Remedy: {self.remedy}"
        )
