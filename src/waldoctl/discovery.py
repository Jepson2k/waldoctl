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
import logging
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint

    from waldoctl.panels import Panel
    from waldoctl.robot import Robot
    from waldoctl.tools import ToolSpec

logger = logging.getLogger(__name__)

_ROBOTS_GROUP = "waldoctl.robots"
_PANELS_GROUP = "waldoctl.panels"
_TOOLS_GROUP = "waldoctl.tools"

# A panel subclass must set these ClassVars; one with any unset is malformed
# and is skipped at discovery so it cannot crash the frontend's panel build.
_REQUIRED_PANEL_CLASSVARS = ("id", "slot", "display_name")

_T = TypeVar("_T")


def _load_entry_point_class(
    listing: dict[str, EntryPoint],
    name: str,
    base: type[_T],
    kind: str,
    not_found_hint: str = "",
) -> type[_T]:
    """Load and validate an entry-point class against *base*.

    *listing* is the group's name→EntryPoint mapping; *kind* names it for the
    not-found message (e.g. ``"Panel plugin"``).

    Raises:
        LookupError: if *name* is not registered.
        TypeError: if the loaded object is not a *base* subclass.
        ImportError: if the entry point's module cannot be imported.
        AttributeError: if the named attribute is missing from the module.
    """
    if name not in listing:
        available = ", ".join(sorted(listing)) or "(none)"
        msg = f"{kind} {name!r} not found. Available: {available}."
        if not_found_hint:
            msg = f"{msg} {not_found_hint}"
        raise LookupError(msg)
    ep = listing[name]
    cls = ep.load()
    if not (isinstance(cls, type) and issubclass(cls, base)):
        raise TypeError(
            f"Entry point {name!r} ({ep.value}) is not a waldoctl.{base.__name__} subclass"
        )
    return cls


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

    return _load_entry_point_class(
        list_backends(),
        name,
        Robot,
        "Robot backend",
        not_found_hint=f"Install with: pip install {name}",
    )


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

    return _load_entry_point_class(list_panels(), name, Panel, "Panel plugin")


def iter_plugin_panels() -> list[type[Panel]]:
    """Return all registered panel classes that are valid ``Panel`` subclasses
    with their required class metadata set.

    Panels are skipped (and logged) when their entry point is invalid (wrong
    base class, unimportable module, typo'd class name) or a required ClassVar
    (``id`` / ``slot`` / ``display_name``) is unset — one broken plugin must not
    prevent others from loading, and callers can use ``cls.id`` / ``cls.slot`` /
    ``cls.display_name`` directly without guards.
    """

    classes: list[type[Panel]] = []
    for name in sorted(list_panels()):
        try:
            cls = load_panel_class(name)
        except (LookupError, TypeError, ImportError, AttributeError) as e:
            logger.warning("Skipping panel plugin %r: %s", name, e)
            continue
        missing = [
            a for a in _REQUIRED_PANEL_CLASSVARS if getattr(cls, a, None) is None
        ]
        if missing:
            logger.warning(
                "Skipping panel plugin %r (%s): unset required ClassVar(s): %s",
                name,
                cls.__name__,
                ", ".join(missing),
            )
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

    return _load_entry_point_class(list_tool_specs(), name, ToolSpec, "Tool spec")
