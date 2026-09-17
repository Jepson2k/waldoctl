"""The dry-run protocol as a runtime question."""

from __future__ import annotations

from typing import Any

import pytest

from waldoctl import is_dry_run


class _Preview:
    def home(self, **kwargs: Any) -> None:
        return None

    def move_j(self, angles=None, **kwargs: Any) -> None:
        return None

    def move_l(self, pose, **kwargs: Any) -> None:
        return None

    def angles(self) -> list[float]:
        return [0.0] * 6

    def pose(self) -> list[float]:
        return [0.0] * 6

    @property
    def tool(self) -> Any:
        raise RuntimeError("No tool set. Call select_tool() first.")

    def flush(self) -> list[Any]:
        return []


class _Forwarding:
    """A wrapper that answers to whatever it wraps, like a preview client or
    the skill guard."""

    def __init__(self, target: object) -> None:
        self._target = target

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._target, name)


class _Live(_Preview):
    """Everything a preview answers except the preview-only member."""

    flush = property(lambda self: (_ for _ in ()).throw(AttributeError("flush")))


@pytest.mark.parametrize(
    ("client", "expected"),
    [
        (_Preview(), True),
        (_Forwarding(_Preview()), True),
        (_Forwarding(_Forwarding(_Preview())), True),
        (_Live(), False),
        (_Forwarding(_Live()), False),
        (object(), False),
    ],
)
def test_is_dry_run_resolves_members_through_forwarding_wrappers(client, expected):
    assert is_dry_run(client) is expected
