"""DryRunClient Protocol — offline motion simulation for path preview."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from waldoctl.results import DryRunResult


@runtime_checkable
class DryRunClient(Protocol):
    """Offline motion client for path preview / dry-run simulation.

    Concrete implementations run the real command pipeline against a
    simulated controller state without hardware.  Each motion method
    returns a ``DryRunResult`` containing the TCP trajectory and final
    joint state.

    Required methods: ``home()``, ``move_j()``, ``move_l()``,
    ``angles()``, ``pose()``, ``flush()``.
    """

    def home(self, **kwargs: Any) -> DryRunResult | None: ...

    def move_j(
        self,
        angles: list[float] | None = None,
        *,
        pose: list[float] | None = None,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        **kwargs: Any,
    ) -> DryRunResult | None: ...

    def move_l(
        self,
        pose: list[float],
        *,
        duration: float = 0.0,
        speed: float = 0.0,
        accel: float = 1.0,
        **kwargs: Any,
    ) -> DryRunResult | None: ...

    def angles(self) -> list[float]: ...

    def pose(self) -> list[float]: ...

    @property
    def tool(self) -> Any: ...

    #: `Sequence`, not `list`: `list` is invariant, so a backend returning
    #: its own concrete result type — which is what every implementation
    #: does — could not satisfy `list[DryRunResult]` no matter how well
    #: the type matched the protocol.
    def flush(self) -> Sequence[DryRunResult]: ...


def is_dry_run(client: object) -> bool:
    """Whether *client* previews rather than drives.

    ``isinstance`` against the protocol looks its members up statically, so a
    client that forwards attribute access -- a preview wrapper, the skill
    guard -- never matches. This asks the way a call would: every public
    protocol member resolves on *client*.
    """
    for name in vars(DryRunClient):
        if name.startswith("_"):
            continue
        try:
            getattr(client, name)
        except AttributeError:
            return False
        except RuntimeError:
            # Present but unable to answer yet, as ``tool`` is before a
            # selection.
            continue
    return True
