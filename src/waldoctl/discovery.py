"""Plugin discovery for waldoctl backends, panels, and tools.

Backends register via the ``waldoctl.robots`` entry-point group::

    [project.entry-points."waldoctl.robots"]
    myrobot = "mypackage.robot:Robot"

GUI panels register via ``waldoctl.panels``::

    [project.entry-points."waldoctl.panels"]
    notes = "mypackage.notes:NotesPanel"

Additional tool specifications register via ``waldoctl.tools``::

    [project.entry-points."waldoctl.tools"]
    laser = "mypackage.laser:LaserTool"

Each entry-point value must reference the corresponding base class
(:class:`waldoctl.Robot`, :class:`waldoctl.Panel`, :class:`waldoctl.ToolSpec`).
"""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint

    from waldoctl.panels import Panel
    from waldoctl.robot import Robot
    from waldoctl.tools import ToolSpec

_ROBOTS_GROUP = "waldoctl.robots"
_PANELS_GROUP = "waldoctl.panels"
_TOOLS_GROUP = "waldoctl.tools"


def list_backends() -> dict[str, EntryPoint]:
    """Return all registered robot backend entry points, keyed by name."""
    return {ep.name: ep for ep in importlib.metadata.entry_points(group=_ROBOTS_GROUP)}


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


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------


def list_panels() -> dict[str, EntryPoint]:
    """Return all registered panel entry points, keyed by name."""
    return {ep.name: ep for ep in importlib.metadata.entry_points(group=_PANELS_GROUP)}


def load_panel_class(name: str) -> type[Panel]:
    """Load and validate a panel class by entry-point name.

    Raises:
        LookupError: if no entry point with *name* is registered.
        TypeError: if the loaded object is not a ``Panel`` subclass.
        ImportError: if the entry point's module cannot be imported.
    """
    from waldoctl.panels import Panel

    panels = list_panels()
    if name not in panels:
        available = ", ".join(sorted(panels)) or "(none)"
        raise LookupError(f"Panel plugin {name!r} not found. Available: {available}.")
    ep = panels[name]
    cls = ep.load()
    if not (isinstance(cls, type) and issubclass(cls, Panel)):
        raise TypeError(
            f"Entry point {name!r} ({ep.value}) is not a waldoctl.Panel subclass"
        )
    return cls


def iter_plugin_panels() -> list[type[Panel]]:
    """Return all registered panel classes, validated as ``Panel`` subclasses.

    Panels with invalid entry points (wrong base class, unimportable module)
    are skipped — one broken plugin must not prevent others from loading.
    """

    classes: list[type[Panel]] = []
    for name in sorted(list_panels()):
        try:
            cls = load_panel_class(name)
        except (LookupError, TypeError, ImportError):
            continue
        classes.append(cls)
    return classes


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def list_tool_specs() -> dict[str, EntryPoint]:
    """Return all registered tool-spec entry points, keyed by name."""
    return {ep.name: ep for ep in importlib.metadata.entry_points(group=_TOOLS_GROUP)}


def load_tool_spec_class(name: str) -> type[ToolSpec]:
    """Load and validate a tool-spec class by entry-point name.

    Raises:
        LookupError: if no entry point with *name* is registered.
        TypeError: if the loaded object is not a ``ToolSpec`` subclass.
        ImportError: if the entry point's module cannot be imported.
    """
    from waldoctl.tools import ToolSpec

    specs = list_tool_specs()
    if name not in specs:
        available = ", ".join(sorted(specs)) or "(none)"
        raise LookupError(f"Tool spec {name!r} not found. Available: {available}.")
    ep = specs[name]
    cls = ep.load()
    if not (isinstance(cls, type) and issubclass(cls, ToolSpec)):
        raise TypeError(
            f"Entry point {name!r} ({ep.value}) is not a waldoctl.ToolSpec subclass"
        )
    return cls
