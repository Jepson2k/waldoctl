"""Controller observations retained independently of any executable trajectory."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal

from waldoctl.setup import validate_name

MAX_RECORDING_SAMPLES = 100_000


def _uint(value: int, label: str) -> None:
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"{label} must be an unsigned 64-bit integer")


def _numbers(values: tuple[float, ...], label: str) -> tuple[float, ...]:
    if len(values) > 32 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in values
    ):
        raise ValueError(f"{label} requires at most 32 finite numbers")
    return tuple(float(v) for v in values)


@dataclass(frozen=True)
class RecordedTool:
    """What the controller reported; position and grasp sensing depend on the tool."""

    key: str
    variant_key: str
    positions: tuple[float, ...]
    engaged: bool
    part_detected: bool
    fault_code: int
    state: int
    channels: tuple[float, ...]

    def __post_init__(self) -> None:
        for name in (self.key, self.variant_key):
            if not isinstance(name, str) or len(name) > 128:
                raise ValueError("Recorded tool identifiers must be bounded strings")
        positions = _numbers(self.positions, "Tool positions")
        if any(not 0 <= value <= 1 for value in positions):
            raise ValueError("Recorded tool positions must be normalized to 0–1")
        object.__setattr__(self, "positions", positions)
        if type(self.engaged) is not bool or type(self.part_detected) is not bool:
            raise ValueError("Recorded tool observations must use boolean flags")
        _uint(self.fault_code, "Tool fault code")
        _uint(self.state, "Tool state")
        object.__setattr__(self, "channels", _numbers(self.channels, "Tool channels"))


@dataclass(frozen=True)
class RecordedSample:
    seq: int
    observed_ns: int
    received_ns: int
    joints_deg: tuple[float, ...]
    tool: RecordedTool | None = None

    def __post_init__(self) -> None:
        _uint(self.seq, "Publication sequence")
        _uint(self.observed_ns, "Controller snapshot time")
        _uint(self.received_ns, "Host receipt time")
        joints = _numbers(self.joints_deg, "Joint observations")
        if not joints:
            raise ValueError("A recorded sample needs joint observations")
        object.__setattr__(self, "joints_deg", joints)
        if self.tool is not None and not isinstance(self.tool, RecordedTool):
            raise ValueError("Invalid recorded tool observation")


RecordingEnd = Literal[
    "stopped",
    "duration_limit",
    "sample_limit",
    "disconnected",
    "session_changed",
    "reference_lost",
    "disabled",
    "tool_changed",
    "source_changed",
    "invalid_observation",
]


@dataclass(frozen=True)
class RecordingGap:
    """The interval ending at ``sample_index`` needs explicit reconciliation."""

    sample_index: int
    missing_publications: int
    elapsed_s: float


@dataclass(frozen=True)
class Demonstration:
    """Timestamped observations, with no implied authorization to replay them.

    ``observed_ns`` belongs to the controller clock, ``received_ns`` to the
    host clock. Their differences describe cadence and delivery respectively;
    subtracting one clock from the other does not measure transport latency.
    """

    backend: str
    session_id: int
    simulator: bool
    tcp_transform: tuple[float, ...]
    requested_rate_hz: float
    gap_threshold_s: float
    ended: RecordingEnd
    samples: tuple[RecordedSample, ...]

    def __post_init__(self) -> None:
        validate_name(self.backend)
        _uint(self.session_id, "Controller session")
        if not self.session_id:
            raise ValueError("A demonstration requires controller session metadata")
        if type(self.simulator) is not bool:
            raise ValueError("The recording source must declare simulator mode")
        tcp = _numbers(self.tcp_transform, "TCP transform")
        if len(tcp) != 6:
            raise ValueError(
                "The applied TCP transform requires six values (mm/degrees)"
            )
        object.__setattr__(self, "tcp_transform", tcp)
        for value in (self.requested_rate_hz, self.gap_threshold_s):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(
                    "Recording cadence settings must be positive and finite"
                )
        if self.ended not in {
            "stopped",
            "duration_limit",
            "sample_limit",
            "disconnected",
            "session_changed",
            "reference_lost",
            "disabled",
            "tool_changed",
            "source_changed",
            "invalid_observation",
        }:
            raise ValueError("Unknown recording termination reason")
        samples = tuple(self.samples)
        if not 1 <= len(samples) <= MAX_RECORDING_SAMPLES:
            raise ValueError(
                f"A demonstration requires 1–{MAX_RECORDING_SAMPLES} samples"
            )
        if any(not isinstance(s, RecordedSample) for s in samples):
            raise ValueError("Invalid recording sample")
        count = len(samples[0].joints_deg)
        for index, sample in enumerate(samples):
            if len(sample.joints_deg) != count:
                raise ValueError("Joint count changed during the recording")
            if index:
                previous = samples[index - 1]
                if (
                    sample.seq <= previous.seq
                    or sample.observed_ns <= previous.observed_ns
                    or sample.received_ns <= previous.received_ns
                ):
                    raise ValueError(
                        "Recording samples must retain their observation order"
                    )
        object.__setattr__(self, "samples", samples)

    @property
    def duration_s(self) -> float:
        return (self.samples[-1].observed_ns - self.samples[0].observed_ns) / 1e9

    @property
    def observed_rate_hz(self) -> float | None:
        return (len(self.samples) - 1) / self.duration_s if self.duration_s else None

    @property
    def gaps(self) -> tuple[RecordingGap, ...]:
        gaps = []
        for index in range(1, len(self.samples)):
            before, after = self.samples[index - 1], self.samples[index]
            missing = after.seq - before.seq - 1
            elapsed = (after.observed_ns - before.observed_ns) / 1e9
            if missing or elapsed > self.gap_threshold_s:
                gaps.append(RecordingGap(index, missing, elapsed))
        return tuple(gaps)

    def select(self, start: int, stop: int) -> Demonstration:
        """Explicitly select a span, retaining every original timestamp."""
        if (
            type(start) is not int
            or type(stop) is not int
            or not 0 <= start < stop <= len(self.samples)
        ):
            raise ValueError("Select a nonempty interval within the recording")
        return replace(self, samples=self.samples[start:stop])

    def require_continuous(self) -> None:
        """Refuse to infer motion through missing observations."""
        if len(self.samples) < 2:
            raise ValueError("Replay requires at least two observations")
        if self.gaps:
            raise ValueError("Select an uninterrupted recording span before replay")
