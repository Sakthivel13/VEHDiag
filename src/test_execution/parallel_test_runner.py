"""Parallel execution of sequences against several ECUs."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from ..core.models.test_sequence_model import TestResult, TestSequence
from ..diagnostics.uds_client import UDSClient
from .test_runner import RunnerOptions, TestRunner

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ECUTarget:
    """One ECU participating in a parallel run.

    Attributes:
        name: Display name of the target.
        client: The UDS client bound to that ECU.
        sequence: Sequence executed against the target.
    """

    name: str
    client: UDSClient
    sequence: TestSequence


@dataclass(slots=True)
class ParallelResult:
    """Results collected for one target."""

    target: str
    results: list[TestResult] = field(default_factory=list)
    error: str = ""

    @property
    def successful(self) -> bool:
        """Return ``True`` when no step failed and no error occurred."""
        from ..core.models.test_sequence_model import TestStatus

        if self.error:
            return False
        return all(r.status not in (TestStatus.FAIL, TestStatus.ERROR) for r in self.results)


class ParallelTestRunner:
    """Execute sequences against several ECUs concurrently.

    Each target gets its own :class:`TestRunner` and therefore its own
    diagnostic session state; the targets must use separate transports.

    Args:
        options: Runner options shared by every target.
        max_workers: Maximum number of concurrent targets.
    """

    def __init__(self, options: RunnerOptions | None = None, max_workers: int = 4) -> None:
        """Create the parallel runner."""
        self.options = options or RunnerOptions()
        self.max_workers = max_workers
        self.runners: dict[str, TestRunner] = {}
        self._lock = threading.RLock()
        self._cancelled = False

    def run(
        self,
        targets: list[ECUTarget],
        on_target_complete: Callable[[ParallelResult], None] | None = None,
    ) -> list[ParallelResult]:
        """Execute every target's sequence concurrently.

        Returns:
            One :class:`ParallelResult` per target, in submission order.
        """
        self._cancelled = False
        results: list[ParallelResult] = []
        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="vdp-par") as pool:
            futures: dict[Future[ParallelResult], ECUTarget] = {}
            for target in targets:
                runner = TestRunner(target.client, self.options)
                runner.load_sequence(target.sequence)
                with self._lock:
                    self.runners[target.name] = runner
                futures[pool.submit(self._run_one, target, runner)] = target
            for future in futures:
                outcome = future.result()
                results.append(outcome)
                if on_target_complete is not None:
                    try:
                        on_target_complete(outcome)
                    except Exception:  # noqa: BLE001
                        _logger.exception("parallel completion callback failed")
        return results

    def _run_one(self, target: ECUTarget, runner: TestRunner) -> ParallelResult:
        """Execute one target's sequence and capture failures."""
        outcome = ParallelResult(target=target.name)
        try:
            outcome.results = runner.execute_all()
        except Exception as exc:  # noqa: BLE001 - reported per target
            outcome.error = str(exc)
            _logger.exception("parallel run failed for %s", target.name)
        return outcome

    def cancel(self) -> None:
        """Cancel every running target."""
        self._cancelled = True
        with self._lock:
            for runner in self.runners.values():
                runner.cancel()

    @property
    def cancelled(self) -> bool:
        """Return ``True`` when a cancel was requested."""
        return self._cancelled

    def summaries(self) -> dict[str, str]:
        """Return the summary text of every target."""
        with self._lock:
            return {name: runner.summary().as_text() for name, runner in self.runners.items()}


__all__ = ["ParallelTestRunner", "ECUTarget", "ParallelResult"]
