"""Function composition, discovery and execution-context behavior."""

import asyncio
import inspect
from dataclasses import dataclass
from importlib.metadata import EntryPoint
from types import SimpleNamespace
from typing import cast

import pytest

from waldoctl.client import RobotClient
from waldoctl.skills import (
    MissingCapability,
    IncompatibleSkill,
    discover_skills,
    observe_skills,
    report_progress,
    skill,
)


@skill(id="test.double", version="1.0.0")
async def double(client: RobotClient, value: int) -> int:
    report_progress("Doubling", fraction=0.5)
    return 2 * value


@skill(id="test.future", version="1.0.0", api_version=2)
async def future_skill(client: RobotClient) -> None:
    pytest.fail("An incompatible runtime must refuse before invoking the body")


def test_nested_functions_keep_arguments_results_events_and_context():
    # No robot operation is performed: this test exercises Python composition.
    client = cast(RobotClient, SimpleNamespace(skill_capabilities=frozenset()))

    @skill(id="test.sum", version="1.0.0")
    async def total(client: RobotClient, *, values: list[int]) -> int:
        return sum([await double.async_call(client, value) for value in values])

    events = []
    with observe_skills(events.append):
        assert asyncio.run(total.async_call(client, values=[2, 3])) == 10
    assert [(e.skill.id, e.phase) for e in events] == [
        ("test.sum", "started"),
        ("test.double", "started"),
        ("test.double", "progress"),
        ("test.double", "completed"),
        ("test.double", "started"),
        ("test.double", "progress"),
        ("test.double", "completed"),
        ("test.sum", "completed"),
    ]
    assert events[1].parent_id == events[0].invocation_id
    assert events[4].parent_id == events[0].invocation_id
    assert events[1].invocation_id != events[4].invocation_id
    assert (
        inspect.signature(total).parameters["values"].kind
        is inspect.Parameter.KEYWORD_ONLY
    )
    assert asyncio.run(double.async_call(client, 4)) == 8
    assert len(events) == 8, "observer must leave the execution context"


def test_capability_failure_and_plugin_conflicts_do_not_execute_or_hide_other_skills(
    monkeypatch, caplog
):
    @skill(id="test.contact", version="1.0.0", requires=frozenset({"motion.contact"}))
    async def contact(client: RobotClient) -> None:
        pytest.fail("Unsupported skill must fail before entering its body")

    client = cast(RobotClient, SimpleNamespace(skill_capabilities=frozenset()))
    events = []
    with (
        observe_skills(events.append),
        pytest.raises(MissingCapability, match="motion.contact"),
    ):
        asyncio.run(contact.async_call(client))
    assert [e.phase for e in events] == ["started", "failed"]

    # EntryPoint.load performs real Python imports, including a broken provider.
    def ep(name, value):
        return EntryPoint(name=name, value=value, group="waldoctl.skills")

    points = [
        ep("good", f"{__name__}:double"),
        ep("broken", "nonexistent_skill_plugin:skill"),
        ep("invalid", "builtins:sum"),
        ep("future", f"{__name__}:future_skill"),
    ]
    monkeypatch.setattr("waldoctl.skills.entry_points", lambda **kwargs: points)
    diagnostics = []
    assert (
        asyncio.run(
            discover_skills(diagnostics=diagnostics)["test.double"].async_call(
                client, 3
            )
        )
        == 6
    )
    assert any("requires skill API 2" in message for message in diagnostics)
    with pytest.raises(IncompatibleSkill, match="requires skill API 2"):
        asyncio.run(future_skill.async_call(client))
    points.append(ep("conflict", f"{__name__}:double"))
    assert "test.double" not in discover_skills()
    assert "all providers excluded" in caplog.text
    assert "Cannot load skill plugin broken" in caplog.text


def test_opt_in_records_bound_arguments_and_results_without_capturing_client():
    @dataclass
    class Outcome:
        positions: list[float]
        token: str

    @skill(id="test.measure", version="1.0.0")
    async def measure(client: RobotClient, positions: list[float], *, scale=2.0):
        positions.append(await double.async_call(client, 3))
        return Outcome([p * scale for p in positions], "private-token")

    client = cast(RobotClient, SimpleNamespace(skill_capabilities=frozenset()))
    positions = [1.0, 2.0]
    detailed, ordinary = [], []
    with (
        observe_skills(detailed.append, capture_values=True),
        observe_skills(ordinary.append),
    ):
        result = asyncio.run(measure.async_call(client, positions))
    assert result.positions == [2.0, 4.0, 12.0]
    assert detailed[0].arguments == {"positions": [1.0, 2.0], "scale": 2.0}
    assert detailed[-1].result == {"positions": [2.0, 4.0, 12.0], "token": "<redacted>"}
    assert detailed[1].arguments == {"value": 3}
    assert all(not event.values_captured for event in ordinary)
    assert all(event.arguments is None and event.result is None for event in ordinary)
    result.positions.clear()
    assert detailed[-1].result["positions"] == [2.0, 4.0, 12.0]
