"""Tests for the ``waldoctl.commander`` locator (PEP 562 __getattr__)."""

from __future__ import annotations

import pytest

import waldoctl
from waldoctl import (
    Commander,
    ProgramTabs,
    RobotStatus,
    Settings,
)


class _StubRobot:
    """Minimal stand-in for a ``Robot`` instance in locator tests."""


class _StubClient:
    """Minimal stand-in for a ``RobotClient`` instance in locator tests."""


@pytest.fixture
def commander() -> Commander:
    """Build a ``Commander`` with stub robot/client and fresh sub-handles."""
    return Commander(
        robot=_StubRobot(),  # type: ignore[arg-type]
        client=_StubClient(),  # type: ignore[arg-type]
        status=RobotStatus(),
        programs=ProgramTabs(),
        settings=Settings(),
    )


@pytest.fixture(autouse=True)
def _clear_locator():
    """Ensure the module-level locator slot is empty before and after each test."""
    waldoctl._clear_commander()
    yield
    waldoctl._clear_commander()


def test_pre_init_access_raises():
    with pytest.raises(RuntimeError, match="not initialised"):
        _ = waldoctl.commander


def test_set_then_access_returns_instance(commander: Commander):
    waldoctl._set_commander(commander)
    assert waldoctl.commander is commander


def test_clear_then_access_raises_again(commander: Commander):
    waldoctl._set_commander(commander)
    assert waldoctl.commander is commander
    waldoctl._clear_commander()
    with pytest.raises(RuntimeError):
        _ = waldoctl.commander


def test_unknown_attribute_still_raises_attribute_error():
    with pytest.raises(AttributeError, match="no attribute 'definitely_not_here'"):
        _ = waldoctl.definitely_not_here
