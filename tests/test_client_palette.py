"""The command-palette docstring contract on ``RobotClient``.

``RobotClient``'s class docstring declares that a method appearing in the
editor's command palette must carry ``Category:`` and ``Example:`` sections,
and that the editor parses these at startup. Sixty-odd docstrings follow the
convention and nothing enforced it: adding a method without ``Category:``
drops it from Waldo-Commander's palette silently, with no error in any repo.
"""

from __future__ import annotations

import inspect

import pytest

from waldoctl import RobotClient


def _documented_methods() -> list[tuple[str, str]]:
    """Public coroutine methods of the ABC that carry a docstring."""
    out = []
    for name, member in inspect.getmembers(RobotClient):
        if name.startswith("_"):
            continue
        doc = inspect.getdoc(member)
        if doc and inspect.iscoroutinefunction(member):
            out.append((name, doc))
    return out


def test_the_abc_actually_has_palette_methods_to_check():
    """Guards the guard: if introspection stops finding methods, every test
    below passes vacuously."""
    assert len(_documented_methods()) > 20


@pytest.mark.parametrize(
    ("name", "doc"), _documented_methods(), ids=[n for n, _ in _documented_methods()]
)
def test_a_palette_method_declares_a_category_and_a_runnable_example(name, doc):
    if "Category:" not in doc:
        pytest.skip(f"{name} is not palette-visible")
    assert "Example:" in doc, (
        f"{name} declares a Category but no Example, so the palette would "
        f"offer it with nothing to insert"
    )
    example = doc.split("Example:", 1)[1].strip()
    first = example.splitlines()[0].strip() if example else ""
    assert first, f"{name}'s Example: block is empty"
    assert "rbt." in first, (
        f"{name}'s Example: first line is what the editor inserts verbatim, "
        f"so it must call the client — got {first!r}"
    )
    assert name in first, (
        f"{name}'s Example: inserts a snippet for a different method ({first!r}), "
        f"which is how a copy-pasted docstring goes unnoticed"
    )
