"""Function composition, discovery and execution-context behavior."""

import asyncio
import inspect
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

    # One capability written as a bare string is refused at declaration. Split
    # into letters it would register and then demand five one-letter
    # capabilities of every client that ran it.
    with pytest.raises(ValueError, match="not one string"):

        @skill(id="test.typo", version="1.0.0", requires="motion.contact")
        async def typo(client: RobotClient) -> None:
            pytest.fail("A skill with a mistyped capability set must not register")

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


def test_skill_timeouts_are_not_cancellation_but_task_cancel_is():
    stops: list[bool] = []

    class Client:
        skill_capabilities = frozenset()

        async def wait_command(self, index: int, timeout: float | None = None):
            await asyncio.sleep(60)

        async def angles(self) -> list[float]:
            return [0.0] * 6

        async def stop(self) -> int:
            stops.append(True)
            return 1

    client = cast(RobotClient, Client())

    @skill(id="test.child", version="1.0.0")
    async def child(rbt: RobotClient) -> bool:
        return await rbt.wait_command(1)

    @skill(id="test.timeouts", version="1.0.0")
    async def timeouts(rbt: RobotClient) -> list[float]:
        # A skill's own deadlines around a supplied-client call and around a
        # nested skill are ordinary control flow, not an invocation cancel.
        try:
            await asyncio.wait_for(rbt.wait_command(1), 0.01)
        except TimeoutError:
            pass
        try:
            async with asyncio.timeout(0.01):
                await child.async_call(rbt)
        except TimeoutError:
            pass
        return await rbt.angles()

    events = []

    async def run() -> None:
        with observe_skills(events.append):
            assert await timeouts.async_call(client) == [0.0] * 6
            assert stops == [], "a timeout inside the skill must not stop the arm"
            task = asyncio.create_task(child.async_call(client))
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run())
    assert stops == [True], "cancelling the invocation stops the arm exactly once"
    phases = [(e.skill.id, e.phase) for e in events]
    assert ("test.timeouts", "completed") in phases
    assert ("test.child", "cancelled") in phases
    assert phases[-1] == ("test.child", "cancelled")
    assert events[-1].stop_confirmed is True
