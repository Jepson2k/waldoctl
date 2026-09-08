"""Explicit Python entry points for a user-selected fresh program run."""

import inspect
from typing import Callable, TypeVar, Any

F = TypeVar("F", bound=Callable[..., Any])


def restart_entry(function: F) -> F:
    """Mark a zero-argument sync/async function; ordinary calls are unchanged.

    This declaration does not authorize continuation, save Python locals or
    perform robot I/O. The host owns fresh-state checks and user selection.
    """
    if not inspect.isfunction(function):
        raise TypeError("A restart entry must be a Python function")
    try:
        inspect.signature(function).bind()
    except TypeError as error:
        raise TypeError("A restart entry must be callable without arguments") from error
    if inspect.isgeneratorfunction(function) or inspect.isasyncgenfunction(function):
        raise TypeError("A restart entry cannot be a generator")
    setattr(function, "__waldo_restart_entry__", True)
    return function


def is_restart_entry(function: object) -> bool:
    return (
        inspect.isfunction(function)
        and getattr(function, "__waldo_restart_entry__", False) is True
    )
