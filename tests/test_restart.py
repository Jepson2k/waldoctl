"""Entry declarations preserve ordinary sync and async function execution."""

import asyncio

import pytest

from waldoctl.restart import restart_entry


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
