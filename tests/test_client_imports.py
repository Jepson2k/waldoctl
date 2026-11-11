"""A robot program loads waldoctl's client without the GUI's libraries."""

from __future__ import annotations

import subprocess
import sys

from nicegui import binding

import waldoctl
from waldoctl import RobotStatus


def _imported_after(code: str) -> set[str]:
    """The top-level packages a fresh interpreter has loaded after ``code``."""
    report = (
        "import sys; print(' '.join(sorted({m.split('.')[0] for m in sys.modules})))"
    )
    out = subprocess.run(
        [sys.executable, "-c", f"{code}\n{report}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return set(out.split())


def test_a_client_process_loads_no_gui_libraries() -> None:
    loaded = _imported_after("import waldoctl, waldoctl.client, waldoctl.tools")
    gui = loaded & {"nicegui", "fastapi", "socketio", "engineio"}
    assert not gui, gui


def test_every_exported_name_resolves() -> None:
    missing = [name for name in waldoctl.__all__ if not hasattr(waldoctl, name)]
    assert not missing


def test_the_status_tool_fires_bindings_at_once() -> None:
    class Readout:
        key = None

    status = RobotStatus()
    readout = Readout()
    binding.bind_from(readout, "key", status.tool, "key")
    status.tool.key = "SSG-48"
    assert readout.key == "SSG-48"
