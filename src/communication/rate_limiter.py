"""Token bucket rate limiting for bus transmissions."""
from __future__ import annotations

import threading
import time


class RateLimiter:
    """Limit how many operations may happen per second.

    The limiter uses a token bucket so short bursts are allowed while the long
    term average stays below the configured rate.

    Example:
        >>> limiter = RateLimiter(messages_per_second=1000)
        >>> limiter.acquire(blocking=False)
        True
    """

    def __init__(self, messages_per_second: float, burst: int | None = None) -> None:
        """Create the limiter.

        Args:
            messages_per_second: Sustained rate; ``0`` disables limiting.
            burst: Bucket capacity, defaults to one second worth of tokens.
        """
        self.rate = float(messages_per_second)
        self.capacity = float(burst if burst is not None else max(1.0, self.rate))
        self._tokens = self.capacity
        self._last = time.perf_counter()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Add tokens accumulated since the previous call."""
        now = time.perf_counter()
        elapsed = now - self._last
        self._last = now
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)

    def acquire(self, tokens: float = 1.0, blocking: bool = True, timeout: float = 5.0) -> bool:
        """Consume *tokens*, optionally waiting until they are available.

        Returns:
            ``True`` when the tokens were consumed.
        """
        if self.rate <= 0:
            return True
        deadline = time.perf_counter() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
                deficit = tokens - self._tokens
                wait = deficit / self.rate
            if not blocking or time.perf_counter() + wait > deadline:
                return False
            time.sleep(min(wait, 0.05))

    def reset(self) -> None:
        """Refill the bucket to its capacity."""
        with self._lock:
            self._tokens = self.capacity
            self._last = time.perf_counter()


__all__ = ["RateLimiter"]
