"""Thread-safe in-memory per-client sliding-window TPS limiter."""
from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class InMemoryTPSLimiter:
    """Enforce a rolling one-second request limit per client."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, client_id: str, limit: int, now: float | None = None) -> bool:
        """Record and allow a request when fewer than ``limit`` occurred recently."""
        if limit < 1:
            return False

        current = monotonic() if now is None else now
        cutoff = current - 1.0
        with self._lock:
            queue = self._events[client_id]
            while queue and queue[0] <= cutoff:
                queue.popleft()
            if len(queue) >= limit:
                return False
            queue.append(current)
            return True

    def reset(self) -> None:
        """Clear all counters; primarily useful for deterministic tests."""
        with self._lock:
            self._events.clear()


limiter = InMemoryTPSLimiter()
