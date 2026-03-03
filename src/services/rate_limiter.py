import asyncio
import time
from collections import defaultdict, deque
from typing import Dict


class RateLimiter:
    def __init__(self, max_requests_per_second: float = 10.0, window_size: float = 1.0):
        self.max_requests_per_second = max_requests_per_second
        self.window_size = window_size
        self.requests: Dict[str, deque] = defaultdict(deque)

    async def acquire(self, user_id: str = "default"):
        now = time.time()
        window_start = now - self.window_size
        while self.requests[user_id] and self.requests[user_id][0] <= window_start:
            self.requests[user_id].popleft()
        if len(self.requests[user_id]) >= self.max_requests_per_second:
            sleep_time = self.requests[user_id][0] + self.window_size - now
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self.requests[user_id].append(now)


rate_limiter = RateLimiter(max_requests_per_second=5.0)
