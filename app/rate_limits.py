"""Small process-local HTTP guardrails for the standalone Android API."""
from __future__ import annotations

import ipaddress
import logging
import time
from collections import defaultdict, deque
from typing import Callable, Hashable


class SlidingWindowLimiter:
    """Bound memory while enforcing fixed per-key sliding windows."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._events: dict[tuple[str, Hashable], deque[float]] = defaultdict(deque)

    def allow(self, bucket: str, key: Hashable, maximum: int, window_seconds: int) -> bool:
        if maximum == 0:
            return True
        now = self._clock()
        events = self._events[(bucket, key)]
        cutoff = now - window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= maximum:
            return False
        events.append(now)
        # Opportunistic cleanup prevents one-off IP/user keys living forever.
        if len(self._events) > 10_000:
            self._events = defaultdict(deque, {
                item_key: values for item_key, values in self._events.items()
                if values and values[-1] > cutoff
            })
        return True


def client_ip(remote: str | None, forwarded_for: str | None) -> str:
    """Trust X-Forwarded-For only from a loopback reverse proxy."""
    try:
        peer = ipaddress.ip_address(str(remote or ""))
    except ValueError:
        return "unknown"
    if peer.is_loopback and forwarded_for:
        candidate = forwarded_for.split(",", 1)[0].strip()
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            logging.warning("Invalid forwarded client address ignored")
    return str(peer)
