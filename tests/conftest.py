"""Shared test fixtures / helpers for the waldoctl test suite."""

from __future__ import annotations

import importlib.metadata

import pytest


def install_fake_entry_points(
    monkeypatch: pytest.MonkeyPatch, group: str, mapping: dict[str, object]
) -> None:
    """Monkeypatch ``importlib.metadata.entry_points`` to return *mapping* for
    *group* (other groups fall through to the real implementation).

    Each mapping value may be a class (resolved to its ``module:qualname``
    entry-point value) or a raw ``"module:attr"`` string — the latter lets a
    test point at a missing / typo'd attribute without defining the class.
    """
    target_group = group
    real = importlib.metadata.entry_points

    def fake(*, group: str = "") -> list[importlib.metadata.EntryPoint]:  # noqa: A002
        if group != target_group:
            return real(group=group) if group else real()
        eps = []
        for name, value in mapping.items():
            ep_value = (
                value
                if isinstance(value, str)
                else f"{value.__module__}:{value.__qualname__}"
            )
            eps.append(
                importlib.metadata.EntryPoint(
                    name=name, value=ep_value, group=target_group
                )
            )
        return eps

    monkeypatch.setattr(importlib.metadata, "entry_points", fake)
