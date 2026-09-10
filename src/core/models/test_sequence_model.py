"""Models describing developer-mode test sequences and their results."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TestStatus(str, Enum):
    """Execution status of a single test step."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"

    @property
    def is_finished(self) -> bool:
        """Return ``True`` when the step will not change state on its own."""
        return self not in (TestStatus.IDLE, TestStatus.RUNNING)

    @property
    def symbol(self) -> str:
        """Return a compact glyph used in tables and logs."""
        return {
            TestStatus.IDLE: "-",
            TestStatus.RUNNING: ">",
            TestStatus.PASS: "PASS",
            TestStatus.FAIL: "FAIL",
            TestStatus.ERROR: "ERR",
            TestStatus.SKIPPED: "SKIP",
            TestStatus.CANCELLED: "CANC",
        }[self]


class ExecutionMode(str, Enum):
    """How a test step should be executed."""

    SCRIPT = "SCRIPT"
    PAYLOAD = "PAYLOAD"
    COMBINED = "COMBINED"


@dataclass(slots=True)
class TestStep:
    """One row of the developer mode service grid.

    Attributes:
        service_id: The UDS SID the step exercises.
        name: Display name of the service.
        payload: Raw request bytes sent in payload mode.
        script_path: Python test script executed in script mode.
        mode: Execution mode of the step.
        enabled: Steps that are disabled are skipped by *Run All*.
        order: Position of the step in the sequence (1-based).
        expected_nrc: When set, the step passes only on this NRC.
    """

    service_id: int
    name: str = ""
    payload: bytes = b""
    script_path: str = ""
    mode: ExecutionMode = ExecutionMode.PAYLOAD
    enabled: bool = True
    order: int = 0
    expected_nrc: int | None = None

    @property
    def payload_hex(self) -> str:
        """Return the payload as space separated uppercase hex."""
        return " ".join(f"{b:02X}" for b in self.payload)

    def as_config(self) -> dict[str, Any]:
        """Return the YAML serialisable representation of the step."""
        return {
            "service": f"0x{self.service_id:02X}",
            "name": self.name,
            "enabled": self.enabled,
            "test_file": self.script_path,
            "payload": self.payload_hex,
            "mode": self.mode.value,
            "order": self.order,
        }

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "TestStep":
        """Build a step from its YAML representation."""
        payload_text = str(data.get("payload", "") or "")
        payload = bytes.fromhex(payload_text.replace(" ", "")) if payload_text else b""
        service = data.get("service", "0x00")
        service_id = int(str(service), 16) if isinstance(service, str) else int(service)
        return cls(
            service_id=service_id,
            name=str(data.get("name", "")),
            payload=payload,
            script_path=str(data.get("test_file", "") or ""),
            mode=ExecutionMode(str(data.get("mode", "PAYLOAD"))),
            enabled=bool(data.get("enabled", True)),
            order=int(data.get("order", 0)),
        )


@dataclass(slots=True)
class TestResult:
    """Outcome of one executed :class:`TestStep`."""

    step: TestStep
    status: TestStatus = TestStatus.IDLE
    duration_ms: float = 0.0
    request: bytes = b""
    response: bytes = b""
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    logs: list[str] = field(default_factory=list)

    def as_row(self) -> dict[str, Any]:
        """Return a flat mapping used by the results table."""
        return {
            "order": self.step.order,
            "service": f"0x{self.step.service_id:02X}",
            "name": self.step.name,
            "file": self.step.script_path,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 2),
            "request": " ".join(f"{b:02X}" for b in self.request),
            "response": " ".join(f"{b:02X}" for b in self.response),
            "details": self.message,
        }


@dataclass(slots=True)
class TestSequence:
    """An ordered collection of test steps plus its execution results."""

    name: str = "Default sequence"
    steps: list[TestStep] = field(default_factory=list)
    results: list[TestResult] = field(default_factory=list)
    stop_on_failure: bool = False

    def reorder(self) -> None:
        """Renumber :attr:`TestStep.order` to match the list order."""
        for index, step in enumerate(self.steps, start=1):
            step.order = index

    def move(self, from_index: int, to_index: int) -> None:
        """Move the step at *from_index* to *to_index* and renumber."""
        if not 0 <= from_index < len(self.steps):
            raise IndexError(f"invalid source index {from_index}")
        to_index = max(0, min(to_index, len(self.steps) - 1))
        self.steps.insert(to_index, self.steps.pop(from_index))
        self.reorder()

    @property
    def enabled_steps(self) -> list[TestStep]:
        """Return only the steps that participate in *Run All*."""
        return [s for s in self.steps if s.enabled]

    def summary(self) -> dict[str, int]:
        """Return counts of each terminal status across :attr:`results`."""
        counts = {status.value: 0 for status in TestStatus}
        for result in self.results:
            counts[result.status.value] += 1
        counts["TOTAL"] = len(self.results)
        return counts

    def as_config(self) -> dict[str, Any]:
        """Return the YAML serialisable representation of the sequence."""
        return {
            "name": self.name,
            "stop_on_failure": self.stop_on_failure,
            "test_sequence": [step.as_config() for step in self.steps],
        }

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "TestSequence":
        """Build a sequence from its YAML representation."""
        steps = [TestStep.from_config(item) for item in data.get("test_sequence", [])]
        steps.sort(key=lambda s: s.order)
        sequence = cls(
            name=str(data.get("name", "Imported sequence")),
            steps=steps,
            stop_on_failure=bool(data.get("stop_on_failure", False)),
        )
        sequence.reorder()
        return sequence


__all__ = ["TestStatus", "ExecutionMode", "TestStep", "TestResult", "TestSequence"]
