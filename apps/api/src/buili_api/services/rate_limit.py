from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class InProcessRateLimiter:
    """Instance-local safety net; Cloudflare remains the distributed production limit."""

    def __init__(self) -> None:
        self.events: dict[str, deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        async with self.lock:
            bucket = self.events[key]
            while bucket and bucket[0] <= now - window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True
