"""``Commander`` — the public locator that gathers every live handle.

The host application (e.g. Waldo-Commander) instantiates this once at
startup and registers it via :func:`waldoctl._set_commander`. Consumers
``import waldoctl`` and reach it through dotted access at call time
(``waldoctl.commander.status.pose.x``, ``waldoctl.commander.programs.active``,
etc.) — never ``from waldoctl import commander``, which resolves the locator
at import time, before the host has registered it.
"""

from __future__ import annotations

from dataclasses import dataclass

from waldoctl.client import RobotClient
from waldoctl.programs import ProgramTabs
from waldoctl.robot import Robot
from waldoctl.robot_status import RobotStatus
from waldoctl.settings import Settings


@dataclass
class Commander:
    """The locator gathering every live handle exposed to API consumers.

    Built once at host-application startup; registered via
    :func:`waldoctl._set_commander`. Same instance reachable from every
    consumer (panels, MCP server, scripts, tests) so writes from one are
    visible to all.

    All fields point at long-lived instances — none are reassigned during
    the session. The sub-handles enforce their own mutate-in-place
    invariants on the nested state they own.
    """

    robot: Robot
    """Live concrete-backend ``Robot`` instance with capabilities (joints,
    tools, limits, frames). Selected at startup from the configured backend."""

    client: RobotClient
    """Live connected control client. Issues motion / IO / tool commands."""

    status: RobotStatus
    """Live robot status. Bindable observation surface populated by the host
    application's status loop."""

    programs: ProgramTabs
    """Open programs container. Each ``Program`` owns its dry-run preview,
    log, execution lifecycle, motion recording, and proposed edits."""

    settings: Settings
    """User-facing preferences and runtime plugin / backend configuration."""
