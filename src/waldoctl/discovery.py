"""Plugin discovery for waldoctl robot backends.

Backends register via the ``waldoctl.robots`` entry-point group in their
``pyproject.toml``::

    [project.entry-points."waldoctl.robots"]
    myrobot = "mypackage.robot:Robot"

The entry-point value must be a :class:`waldoctl.Robot` subclass.
"""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint

    from waldoctl.robot import Robot

_GROUP = "waldoctl.robots"


def list_backends() -> dict[str, EntryPoint]:
    """Return all registered robot backend entry points, keyed by name."""
    return {ep.name: ep for ep in importlib.metadata.entry_points(group=_GROUP)}


def available_backends() -> list[str]:
    """Return sorted list of registered backend names."""
    return sorted(list_backends())


def load_robot_class(name: str) -> type[Robot]:
    """Load and validate a robot backend class by entry-point name.

    Raises:
        LookupError: if no entry point with *name* is registered.
        TypeError: if the loaded object is not a ``Robot`` subclass.
        ImportError: if the entry point's module cannot be imported.
    """
    from waldoctl.robot import Robot

    backends = list_backends()
    if name not in backends:
        available = ", ".join(sorted(backends)) or "(none)"
        raise LookupError(
            f"Robot backend {name!r} not found. Available: {available}. "
            f"Install with: pip install {name}"
        )
    ep = backends[name]
    cls = ep.load()
    if not (isinstance(cls, type) and issubclass(cls, Robot)):
        raise TypeError(
            f"Entry point {name!r} ({ep.value}) is not a waldoctl.Robot subclass"
        )
    return cls


def get_robot(name: str, **kwargs: object) -> Robot:
    """Load a backend class and instantiate it.

    *kwargs* are forwarded to the Robot subclass constructor.
    """
    cls = load_robot_class(name)
    return cls(**kwargs)
