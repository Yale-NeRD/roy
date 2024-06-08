import asyncio
import ray
from collections import deque

@ray.remote
class RoyLock:
    def __init__(self):
        self._is_locked = False
        self._queue = deque()
        self._condition = asyncio.Condition()

    async def lock(self):
        async with self._condition:
            current_task = asyncio.current_task()
            self._queue.append(current_task)
            while self._is_locked or self._queue[0] != current_task:
                await self._condition.wait()
            self._queue.popleft()
            self._is_locked = True
            # print("Lock acquired", flush=True)
            return True

    async def unlock(self):
        async with self._condition:
            self._is_locked = False
            self._condition.notify_all()
            # print("Lock released", flush=True)
            return True
