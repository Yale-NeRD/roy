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
        '''
        - The current owner is located at self._queue[0]
        '''
        async with self._condition:
            current_task = asyncio.current_task()
            self._queue.append(current_task)
            # print(f"Lock requested: {self._queue}", flush=True)
            while self._is_locked:
                if self._queue[0] == current_task:
                    break
                await self._condition.wait()
                # print(f"\nLock check: {current_task}\nin {self._queue}", flush=True)
            self._is_locked = True
            # print(f"Lock acquired: {current_task}", flush=True)
            return True

    async def try_lock(self):
        async with self._condition:
            # Assumption: actor is not multi-threaded
            if self._is_locked:
                return False
            self._is_locked = True
            return True

    async def unlock(self):
        async with self._condition:
            # Assumption: actor is not multi-threaded
            # If so, in the future impl., we will need a local lock
            self._queue.popleft()
            if len(self._queue) == 0:
                self._is_locked = False
            # print(f"Lock released: {self._queue}", flush=True)
            self._condition.notify_all()
            return True
