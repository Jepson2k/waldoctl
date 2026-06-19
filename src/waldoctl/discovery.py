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
from typing import TYPE_CHECKING, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable
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
    return _validate_entry_point(name, listing[name], base)


def _validate_entry_point(name: str, ep: EntryPoint, base: type[_T]) -> type[_T]:
    """Load an already-resolved EntryPoint and type-check it against *base*.

    Split out so the ``iter_plugin_*`` discovery loops can validate each
    EntryPoint from a single group listing instead of re-listing the whole
    group per name. Raises ``TypeError`` if the object isn't a *base* subclass;
    ``ep.load()`` may raise ``ImportError`` / ``AttributeError`` and, since it
    runs third-party module code, anything else.
    """
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
        AttributeError: if the named attribute is missing from the module.
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
        AttributeError: if the named attribute is missing from the module.
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

    from waldoctl.panels import Panel, PanelSlot

    classes: list[type[Panel]] = []
    seen_ids: set[str] = set()
    # Iterate the group listing once. ``ep.load()`` runs arbitrary third-party
    # module code, so catch broadly and skip — one misbehaving plugin must not
    # take down the host's panel build.
    for name, ep in sorted(list_panels().items()):
        try:
            cls = _validate_entry_point(name, ep, Panel)
        except Exception as e:  # noqa: BLE001 — third-party import boundary
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
        if not isinstance(cls.slot, PanelSlot):
            logger.warning(
                "Skipping panel plugin %r (%s): slot %r is not a PanelSlot",
                name,
                cls.__name__,
                cls.slot,
            )
            continue
        if cls.id in seen_ids:
            logger.warning(
                "Skipping panel plugin %r (%s): duplicate id %r already registered",
                name,
                cls.__name__,
                cls.id,
            )
            continue
        seen_ids.add(cls.id)
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
        AttributeError: if the named attribute is missing from the module.
    """
    from waldoctl.tools import ToolSpec

    return _load_entry_point_class(list_tool_specs(), name, ToolSpec, "Tool spec")


def iter_plugin_tools() -> list[type[ToolSpec]]:
    """Return registered ``ToolSpec`` classes from ``waldoctl.tools``, skipping
    (and logging) any whose entry point is invalid. Mirrors
    :func:`iter_plugin_panels`."""
    from waldoctl.tools import ToolSpec

    classes: list[type[ToolSpec]] = []
    # Single group listing; broad catch around the third-party load boundary.
    for name, ep in sorted(list_tool_specs().items()):
        try:
            cls = _validate_entry_point(name, ep, ToolSpec)
        except Exception as e:  # noqa: BLE001 — third-party import boundary
            logger.warning("Skipping tool plugin %r: %s", name, e)
            continue
        classes.append(cls)
    return classes


def iter_plugin_tool_specs() -> list[ToolSpec]:
    """Instantiate the ``waldoctl.tools`` entry-point classes, skipping (and
    logging) any that fail. Tool-spec classes must be zero-arg constructible."""
    specs: list[ToolSpec] = []
    for cls in iter_plugin_tools():
        ctor = cast("Callable[[], ToolSpec]", cls)
        try:
            specs.append(ctor())
        except Exception as e:
            logger.warning("Plugin tool %s failed to instantiate: %s", cls, e)
    return specs
