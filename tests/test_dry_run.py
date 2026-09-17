"""The dry-run protocol as a runtime question."""

from __future__ import annotations

from typing import Any


from waldoctl import is_dry_run
from waldoctl.dry_run import DryRunClient


def _members() -> list[str]:
    return [name for name in vars(DryRunClient) if not name.startswith("_")]


def _preview_type(*, without: str | None = None) -> type:
    """A client answering to the protocol as this layer declares it, with
    ``tool`` refusing the way a client does before a selection."""
    body: dict[str, Any] = {}
    for name in _members():
        if name == without:
            continue
        if name == "tool":
            body[name] = property(
                lambda self: (_ for _ in ()).throw(
                    RuntimeError("No tool set. Call select_tool() first.")
                )
            )
        else:
            body[name] = lambda self, *args, **kwargs: None
    return type("_Preview", (), body)


class _Forwarding:
    """A wrapper that answers to whatever it wraps, like a preview client or
    the skill guard."""

    def __init__(self, target: object) -> None:
        self._target = target

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._target, name)


def test_is_dry_run_resolves_members_through_forwarding_wrappers():
    preview = _preview_type()()
    assert is_dry_run(preview)
    assert is_dry_run(_Forwarding(preview))
    assert is_dry_run(_Forwarding(_Forwarding(preview)))

    live = _preview_type(without="flush")()
    assert not is_dry_run(live)
    assert not is_dry_run(_Forwarding(live))
    assert not is_dry_run(object())
