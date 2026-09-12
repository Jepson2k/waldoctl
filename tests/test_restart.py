"""Entry declarations preserve ordinary sync and async function execution."""

import asyncio
import functools

import pytest

from waldoctl.restart import is_restart_entry, restart_entry


def test_entry_calls_preserve_results_and_reject_unusable_signatures():
    @restart_entry
    def count(value=4):
        return value + 1

    @restart_entry
    async def composed():
        return count(8)

    assert count() == 5
    assert asyncio.run(composed()) == 9

    def requires_argument(value):
        return value

    def generator():
        yield count()

    async def async_generator():
        yield count()

    for function in (requires_argument, generator, async_generator):
        with pytest.raises(TypeError):
            restart_entry(function)

    # The marker is the whole contract a frontend reads: Commander refuses to
    # launch anything `is_restart_entry` does not recognise, so renaming the
    # attribute would leave this suite green and every restart launch failing.
    assert is_restart_entry(count) and is_restart_entry(composed)
    assert not is_restart_entry(requires_argument)
    assert not is_restart_entry(lambda: None)
    assert not is_restart_entry(count())  # a value, not the entry

    @restart_entry
    @functools.wraps(count)
    def wrapped():
        return count()

    assert is_restart_entry(wrapped), "the marker survives functools.wraps"
