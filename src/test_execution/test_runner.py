"""Main test execution engine.

The runner executes :class:`TestStep` objects in three modes:

* ``PAYLOAD`` - transmit the raw bytes stored in the step and judge the answer,
* ``SCRIPT``  - import the mapped Python file and run its ``TestScript`` class,
* ``COMBINED`` - run the script first, then verify with the payload.

Execution always happens on the calling thread; the UI runs the runner inside a
``QThread`` and receives updates through the callbacks and the event bus.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

from ..core.event_bus import EventBus, EventType, get_event_bus
from ..core.interfaces.i_test_runner import ITestRunner
from ..core.models.test_sequence_model import (
    ExecutionMode,
    TestResult,
    TestSequence,
    TestStatus,
    TestStep,
)
from ..diagnostics.uds_client import UDSClient
from ..utils.timer_utils import Stopwatch
from .scripts.base_test_script import normalise_result
from .scripts.script_api import AssertionFailure, DiagnosticAPI, ScriptContext
from .test_result_collector import ResultSummary, TestResultCollector
from .test_script_loader import TestScriptLoader

_logger = logging.getLogger(__name__)

#: Callback invoked when a step starts or finishes.
StepCallback = Callable[[TestStep, TestResult | None], None]


@dataclass(slots=True)
class RunnerOptions:
    """Behaviour of one execution run.

    Attributes:
        stop_on_failure: Abort the sequence at the first failure.
        skip_disabled: Skip steps whose ``enabled`` flag is false.
        default_timeout_s: Timeout applied to payload mode requests.
        inter_step_delay_ms: Pause inserted between two steps.
        run_setup_teardown: Call ``setup``/``teardown`` of script mode steps.
    """

    stop_on_failure: bool = False
    skip_disabled: bool = True
    default_timeout_s: float = 2.0
    inter_step_delay_ms: float = 0.0
    run_setup_teardown: bool = True


class TestRunner(ITestRunner):
    """Execute single steps or whole sequences against a UDS client.

    Args:
        client: The UDS client the tests drive.
        options: Execution behaviour.
        event_bus: Bus used to publish execution events.
        on_step: Callback receiving ``(step, result)``; ``result`` is ``None``
            when the step starts.

    Example:
        >>> # runner = TestRunner(client)
        >>> # runner.load_sequence(sequence)
        >>> # results = runner.execute_all()
        >>> None
    """

    def __init__(
        self,
        client: UDSClient,
        options: RunnerOptions | None = None,
        event_bus: EventBus | None = None,
        on_step: StepCallback | None = None,
    ) -> None:
        """Create the runner in the idle state."""
        self.client = client
        self.options = options or RunnerOptions()
        self.bus = event_bus or get_event_bus()
        self.on_step = on_step
        self.loader = TestScriptLoader()
        self.collector = TestResultCollector()
        self.context = ScriptContext()
        self.api = DiagnosticAPI(client, self.context)
        self.sequence = TestSequence()
        self._status = TestStatus.IDLE
        self._current_step: TestStep | None = None
        self._cancel = threading.Event()
        self._lock = threading.RLock()

    # -- ITestRunner --------------------------------------------------------
    def load_sequence(self, sequence: TestSequence) -> None:
        """Load the sequence executed by :meth:`execute_all`."""
        with self._lock:
            self.sequence = sequence
            self.sequence.reorder()

    def load_script(self, path: str) -> type:
        """Import a script file and return its ``TestScript`` class."""
        return self.loader.load(path).script_class

    def cancel(self) -> None:
        """Request a graceful abort of the running sequence."""
        self._cancel.set()
        self.context.cancelled = True
        self.bus.publish(EventType.TEST_CANCELLED, {}, "TestRunner")

    def get_status(self) -> TestStatus:
        """Return the status of the current or last step."""
        return self._status

    def get_results(self) -> list[TestResult]:
        """Return every result collected so far."""
        return list(self.collector.results)

    # -- execution ------------------------------------------------------------
    def execute_step(self, step: TestStep) -> TestResult:
        """Run one *step* and return its result."""
        result = TestResult(step=step, status=TestStatus.RUNNING)
        self._current_step = step
        self._status = TestStatus.RUNNING
        self._notify(step, None)
        self.bus.publish(
            EventType.TEST_STEP_STARTED,
            {"service": step.service_id, "name": step.name, "order": step.order},
            "TestRunner",
        )
        watch = Stopwatch().start()
        try:
            if self._cancel.is_set():
                result.status = TestStatus.CANCELLED
                result.message = "cancelled before execution"
            elif step.mode is ExecutionMode.SCRIPT:
                self._run_script(step, result)
            elif step.mode is ExecutionMode.PAYLOAD:
                self._run_payload(step, result)
            else:
                self._run_script(step, result)
                if result.status is TestStatus.PASS and step.payload:
                    self._run_payload(step, result)
        except AssertionFailure as exc:
            result.status = TestStatus.FAIL
            result.message = str(exc)
        except Exception as exc:  # noqa: BLE001 - a script must not crash the app
            result.status = TestStatus.ERROR
            result.message = f"{type(exc).__name__}: {exc}"
            _logger.exception("test step raised")
        finally:
            result.duration_ms = watch.stop()
            result.logs = list(self.context.logs)
            self.context.logs.clear()
            self._status = result.status
            self._current_step = None

        self.collector.add(result)
        self._notify(step, result)
        self.bus.publish(
            EventType.TEST_STEP_COMPLETED,
            {
                "service": step.service_id,
                "name": step.name,
                "status": result.status.value,
                "duration_ms": result.duration_ms,
                "message": result.message,
            },
            "TestRunner",
        )
        if result.status in (TestStatus.FAIL, TestStatus.ERROR):
            self.bus.publish(
                EventType.TEST_FAILED,
                {"name": step.name, "message": result.message},
                "TestRunner",
            )
        return result

    def execute_all(self) -> list[TestResult]:
        """Run every enabled step of the loaded sequence in order."""
        self._cancel.clear()
        self.context.cancelled = False
        self.collector.start()
        steps = self.sequence.enabled_steps if self.options.skip_disabled else self.sequence.steps
        self.bus.publish(
            EventType.TEST_STARTED,
            {"sequence": self.sequence.name, "steps": len(steps)},
            "TestRunner",
        )
        for index, step in enumerate(steps):
            if self._cancel.is_set():
                for remaining in steps[index:]:
                    cancelled = TestResult(step=remaining, status=TestStatus.CANCELLED,
                                           message="cancelled")
                    self.collector.add(cancelled)
                    self._notify(remaining, cancelled)
                break
            result = self.execute_step(step)
            stop = self.options.stop_on_failure or self.sequence.stop_on_failure
            if stop and result.status in (TestStatus.FAIL, TestStatus.ERROR):
                for remaining in steps[index + 1 :]:
                    skipped = TestResult(step=remaining, status=TestStatus.SKIPPED,
                                         message="skipped after a failure")
                    self.collector.add(skipped)
                    self._notify(remaining, skipped)
                break
            if self.options.inter_step_delay_ms:
                time.sleep(self.options.inter_step_delay_ms / 1000.0)

        summary = self.collector.finish()
        self.sequence.results = list(self.collector.results)
        self.bus.publish(
            EventType.TEST_SEQUENCE_COMPLETE,
            {
                "total": summary.total,
                "passed": summary.passed,
                "failed": summary.failed,
                "errors": summary.errors,
                "duration_ms": summary.duration_ms,
                "successful": summary.successful,
            },
            "TestRunner",
        )
        self.bus.publish(EventType.TEST_COMPLETED, {"summary": summary.as_text()}, "TestRunner")
        _logger.info("%s", summary.as_text())
        return self.get_results()

    def run_single(self, index: int) -> TestResult:
        """Run only the step at *index* of the loaded sequence.

        Raises:
            IndexError: The index is out of range.
        """
        step = self.sequence.steps[index]
        self._cancel.clear()
        self.context.cancelled = False
        return self.execute_step(step)

    # -- mode implementations ------------------------------------------------------
    def _run_payload(self, step: TestStep, result: TestResult) -> None:
        """Send the raw payload of *step* and judge the response."""
        if not step.payload:
            result.status = TestStatus.SKIPPED
            result.message = "no payload configured"
            return
        response = self.client.send_request(
            step.payload, timeout=self.options.default_timeout_s
        )
        result.request = step.payload
        result.response = response.raw
        if step.expected_nrc is not None:
            if response.is_negative and response.nrc == step.expected_nrc:
                result.status = TestStatus.PASS
                result.message = f"expected NRC 0x{step.expected_nrc:02X} received"
            else:
                result.status = TestStatus.FAIL
                result.message = (
                    f"expected NRC 0x{step.expected_nrc:02X}, got {response.summary()}"
                )
            return
        if response.is_positive():
            result.status = TestStatus.PASS
            result.message = response.summary()
        else:
            result.status = TestStatus.FAIL
            result.message = response.summary()

    def _run_script(self, step: TestStep, result: TestResult) -> None:
        """Import and execute the script mapped to *step*."""
        if not step.script_path:
            result.status = TestStatus.SKIPPED
            result.message = "no test script mapped"
            return
        loaded = self.loader.load(step.script_path)
        instance = loaded.instantiate(self.api)
        if self.options.run_setup_teardown and hasattr(instance, "setup"):
            instance.setup()
        try:
            outcome = instance.execute()
            result.status = normalise_result(outcome)
            result.message = result.message or f"script returned {outcome!r}"
        finally:
            if self.options.run_setup_teardown and hasattr(instance, "teardown"):
                try:
                    instance.teardown()
                except Exception:  # noqa: BLE001 - teardown must not mask the result
                    _logger.exception("teardown of %s failed", loaded.name)
        last = self.api.get_last_response()
        if last is not None:
            result.request = last.request
            result.response = last.raw

    # -- helpers -------------------------------------------------------------------
    def summary(self) -> ResultSummary:
        """Return the aggregated summary of the last run."""
        return self.collector.summary()

    def clear_results(self) -> None:
        """Discard the collected results."""
        self.collector.clear()
        self._status = TestStatus.IDLE

    @property
    def is_running(self) -> bool:
        """Return ``True`` while a step is being executed."""
        return self._status is TestStatus.RUNNING

    @property
    def current_step(self) -> TestStep | None:
        """Return the step currently being executed."""
        return self._current_step

    def _notify(self, step: TestStep, result: TestResult | None) -> None:
        """Invoke the step callback, ignoring its exceptions."""
        if self.on_step is None:
            return
        try:
            self.on_step(step, result)
        except Exception:  # noqa: BLE001
            _logger.exception("test runner step callback failed")


__all__ = ["TestRunner", "RunnerOptions", "StepCallback"]
