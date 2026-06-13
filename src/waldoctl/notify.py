"""``ChangeNotifierMixin`` — a cross-cutting two-channel observer primitive.

Used by the live-status, settings, programs, and dry-run dataclasses for the
mutations ``bindable_dataclass`` can't express. It lives in its own module so
those unrelated domains don't depend on ``robot_status`` just for the mixin.
"""

from __future__ import annotations

from typing import Callable


class ChangeNotifierMixin:
    """Two-channel listener pattern for cases ``bindable_dataclass`` can't
    express on its own.

    ``bindable_dataclass`` fires UI bindings on field *reassignment*. In-place
    mutations (``list.append``, ``arr[:] = ...``, nested attribute writes,
    multi-field state transitions) do not fire bindings; the mutator should
    call :meth:`notify_changed` so any registered listener can react.

    Two channels are exposed so high-frequency step events (e.g. a running
    script advancing through waypoints at ~20 Hz) can fan out to a small set
    of observers without forcing the broader change-listener chain to recompute:

    - **change channel** — ``add_change_listener`` / ``remove_change_listener`` /
      :meth:`notify_changed`. Broad state mutations; everyone subscribes.
    - **step channel** — ``add_step_listener`` / ``remove_step_listener`` /
      :meth:`notify_step_changed`. Hot script-step events; only playback /
      step-aware consumers subscribe.

    The lists are built lazily on first registration, so subclasses do not
    need to redeclare them as dataclass fields. Copy-on-write storage lets
    each ``notify_*`` iterate safely while new listeners are being added.

    ``remove_*`` uses ``!=`` (not ``is not``) so bound methods are removable
    by their function reference — each ``obj.method`` access creates a fresh
    bound-method object that fails ``is`` but compares equal by
    ``(instance, func)``.
    """

    def _get_listeners(self) -> list[Callable[[], None]]:
        try:
            return self._change_listeners  # type: ignore[attr-defined]
        except AttributeError:
            self._change_listeners: list[Callable[[], None]] = []
            return self._change_listeners

    def _get_step_listeners(self) -> list[Callable[[], None]]:
        try:
            return self._step_listeners  # type: ignore[attr-defined]
        except AttributeError:
            self._step_listeners: list[Callable[[], None]] = []
            return self._step_listeners

    def add_change_listener(self, callback: Callable[[], None]) -> None:
        listeners = self._get_listeners()
        if callback not in listeners:
            self._change_listeners = [*listeners, callback]

    def remove_change_listener(self, callback: Callable[[], None]) -> None:
        self._change_listeners = [cb for cb in self._get_listeners() if cb != callback]

    def notify_changed(self) -> None:
        for cb in self._get_listeners():
            cb()

    def add_step_listener(self, callback: Callable[[], None]) -> None:
        listeners = self._get_step_listeners()
        if callback not in listeners:
            self._step_listeners = [*listeners, callback]

    def remove_step_listener(self, callback: Callable[[], None]) -> None:
        self._step_listeners = [
            cb for cb in self._get_step_listeners() if cb != callback
        ]

    def notify_step_changed(self) -> None:
        for cb in self._get_step_listeners():
            cb()
