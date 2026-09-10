"""Integration tests for the developer mode execution engine."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from src.core.models.test_sequence_model import ExecutionMode, TestStatus, TestStep
from src.test_execution.test_runner import RunnerOptions, TestRunner
from src.test_execution.test_sequence_manager import TestSequenceManager

pytestmark = pytest.mark.integration

#: Directory holding the bundled sample scripts.
SAMPLES = Path(__file__).resolve().parents[2] / "sample_test_scripts"


class TestPayloadMode:
    """Running steps that only send a payload."""

    def test_default_sequence_passes(self, client) -> None:
        """Every enabled step of the default sequence succeeds."""
        manager = TestSequenceManager()
        sequence = manager.create_default()
        runner = TestRunner(client)
        runner.load_sequence(sequence)
        results = runner.execute_all()
        assert results
        summary = runner.summary()
        assert summary.failed == 0
        assert summary.errors == 0

    def test_expected_nrc(self, client) -> None:
        """A step can require a specific negative response."""
        step = TestStep(
            service_id=0x22,
            name="Unsupported DID",
            payload=bytes.fromhex("22FFFF"),
            expected_nrc=0x31,
        )
        runner = TestRunner(client)
        assert runner.execute_step(step).status is TestStatus.PASS

    def test_failure_is_reported(self, client) -> None:
        """An unexpected negative response fails the step."""
        step = TestStep(service_id=0x22, name="Unsupported DID",
                        payload=bytes.fromhex("22FFFF"))
        assert TestRunner(client).execute_step(step).status is TestStatus.FAIL

    def test_stop_on_failure(self, client) -> None:
        """Remaining steps are skipped after a failure."""
        sequence = TestSequenceManager().create_empty()
        sequence.steps = [
            TestStep(0x22, "bad", bytes.fromhex("22FFFF"), order=1),
            TestStep(0x10, "session", bytes.fromhex("1003"), order=2),
        ]
        runner = TestRunner(client, RunnerOptions(stop_on_failure=True))
        runner.load_sequence(sequence)
        results = runner.execute_all()
        assert results[0].status is TestStatus.FAIL
        assert results[1].status is TestStatus.SKIPPED

    def test_disabled_steps_are_skipped(self, client) -> None:
        """Disabled steps never run."""
        sequence = TestSequenceManager().create_empty()
        sequence.steps = [
            TestStep(0x10, "enabled", bytes.fromhex("1003"), enabled=True, order=1),
            TestStep(0x10, "disabled", bytes.fromhex("1001"), enabled=False, order=2),
        ]
        runner = TestRunner(client)
        runner.load_sequence(sequence)
        assert len(runner.execute_all()) == 1


class TestScriptMode:
    """Running mapped Python test scripts."""

    @pytest.mark.parametrize(
        "script",
        ["read_all_dids.py", "read_all_dtcs.py", "security_unlock.py", "clear_all_dtcs.py",
         "eol_test_sequence.py"],
    )
    def test_sample_scripts_pass(self, client, script: str) -> None:
        """Every bundled sample script passes against the simulator."""
        step = TestStep(
            service_id=0x22,
            name=script,
            script_path=str(SAMPLES / script),
            mode=ExecutionMode.SCRIPT,
        )
        result = TestRunner(client).execute_step(step)
        assert result.status is TestStatus.PASS, result.message

    def test_script_logs_are_captured(self, client) -> None:
        """Messages written with ``api.log`` end up in the result."""
        step = TestStep(
            service_id=0x22,
            name="read_all_dids",
            script_path=str(SAMPLES / "read_all_dids.py"),
            mode=ExecutionMode.SCRIPT,
        )
        result = TestRunner(client).execute_step(step)
        assert any("VIN" in line for line in result.logs)

    def test_broken_script_reports_error(self, client, tmp_path: Path) -> None:
        """A script raising an exception yields the ERROR status."""
        script = tmp_path / "broken.py"
        script.write_text(
            "class TestScript:\n"
            "    def __init__(self, api): self.api = api\n"
            "    def execute(self): raise RuntimeError('boom')\n"
        )
        step = TestStep(0x22, "broken", script_path=str(script), mode=ExecutionMode.SCRIPT)
        result = TestRunner(client).execute_step(step)
        assert result.status is TestStatus.ERROR
        assert "boom" in result.message

    def test_assertion_failure_reports_fail(self, client, tmp_path: Path) -> None:
        """A failed assertion yields the FAIL status."""
        script = tmp_path / "assert.py"
        script.write_text(
            "class TestScript:\n"
            "    def __init__(self, api): self.api = api\n"
            "    def execute(self):\n"
            "        self.api.send_hex('22 FF FF')\n"
            "        self.api.assert_positive_response('expected the DID to be readable')\n"
        )
        step = TestStep(0x22, "assert", script_path=str(script), mode=ExecutionMode.SCRIPT)
        result = TestRunner(client).execute_step(step)
        assert result.status is TestStatus.FAIL
        assert "expected the DID" in result.message

    def test_invalid_script_is_rejected(self, client, tmp_path: Path) -> None:
        """A script without a TestScript class cannot be loaded."""
        script = tmp_path / "empty.py"
        script.write_text("x = 1\n")
        step = TestStep(0x22, "empty", script_path=str(script), mode=ExecutionMode.SCRIPT)
        assert TestRunner(client).execute_step(step).status is TestStatus.ERROR


class TestCancellation:
    """Cancelling a running sequence."""

    def test_cancel_marks_remaining_steps(self, client, tmp_path: Path) -> None:
        """Cancelling stops the run and marks the rest as cancelled."""
        slow = tmp_path / "slow.py"
        slow.write_text(
            "class TestScript:\n"
            "    def __init__(self, api): self.api = api\n"
            "    def execute(self):\n"
            "        self.api.wait(3000)\n"
            "        return 'PASS'\n"
        )
        sequence = TestSequenceManager().create_empty()
        sequence.steps = [
            TestStep(0x22, f"slow {i}", script_path=str(slow), mode=ExecutionMode.SCRIPT, order=i)
            for i in range(1, 4)
        ]
        runner = TestRunner(client)
        runner.load_sequence(sequence)

        results: list = []
        thread = threading.Thread(target=lambda: results.extend(runner.execute_all()))
        thread.start()
        time.sleep(0.4)
        started = time.perf_counter()
        runner.cancel()
        thread.join(5)
        assert time.perf_counter() - started < 2.0
        assert any(r.status in (TestStatus.CANCELLED, TestStatus.FAIL) for r in results)


class TestSequencePersistence:
    """Saving and loading sequences."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """A sequence survives a save and load cycle."""
        manager = TestSequenceManager()
        sequence = manager.create_default()
        sequence.name = "My sequence"
        path = manager.save(sequence, tmp_path / "sequence.yaml")
        loaded = manager.load(path)
        assert loaded.name == "My sequence"
        assert len(loaded.steps) == len(sequence.steps)
        assert loaded.steps[0].payload == sequence.steps[0].payload

    def test_reordering(self) -> None:
        """Moving a step renumbers the sequence."""
        manager = TestSequenceManager()
        sequence = manager.create_default()
        first = sequence.steps[0].name
        manager.move(sequence, 0, 3)
        assert sequence.steps[3].name == first
        assert [step.order for step in sequence.steps] == list(range(1, len(sequence.steps) + 1))

    def test_duplicate_and_remove(self) -> None:
        """Steps can be duplicated and removed."""
        manager = TestSequenceManager()
        sequence = manager.create_default()
        count = len(sequence.steps)
        manager.duplicate_step(sequence, 0)
        assert len(sequence.steps) == count + 1
        manager.remove_step(sequence, 1)
        assert len(sequence.steps) == count
