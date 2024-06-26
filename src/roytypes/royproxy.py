import ray
import asyncio
from enum import Enum

class CacheState(Enum):
    INVALID = 0
    SHARED = 1
    MODIFIED = 2

class CachePermission(Enum):
    INVALID = 0
    READ = 1
    WRITE = 2
    EVICT = 8

def gen_roy_id():
    roy_id = str(ray.get_runtime_context().get_worker_id())
    # print(f"Generated Roy ID: {roy_id}", flush=True)
    return roy_id

class RoyRequester:
    '''
    Store the requester information
    @requester: str - ray id or handle of the requester actor
    @invalidate_handle: asyncio.event - the event to trigger the invalidation
    '''
    def __init__(self, requester: str, invalidate_handle=None):
        self.requester = requester
        self.invalidate_handle = invalidate_handle

    def __hash__(self) -> int:
        self.requester.__hash__()

class RoyCache:
    def __init__(self) -> None:
        self._cache_state = CacheState.INVALID

    def transition(self, requester, permission: CachePermission):
        raise NotImplementedError

class RoyCacheDirMSI(RoyCache):
    def __init__(self) -> None:
        super().__init__()
        self._cache_sharer = dict() # requester id -> asyncio.event
        self._waiting_data_ok = asyncio.Event()
        self._waiting_data_ok.set()

    def process_evict(self, requester):
        if requester in self._cache_sharer.keys():
            async_handle = self._cache_sharer.pop(requester)
            if async_handle:
                async_handle.set()
        if self._cache_state == CacheState.MODIFIED:
            if not self._waiting_data_ok.is_set():
                self._waiting_data_ok.set()  # data received => set
            self._cache_state = CacheState.INVALID
        else:
            if len(self._cache_sharer) == 0:
                self._cache_state = CacheState.INVALID
            else:
                self._cache_state = CacheState.SHARED

    async def process_fetch(self, requester, permission: CachePermission):
        await self._waiting_data_ok.wait()
        # NOTE) we assume that the lock only allows compatible concurrent requests.
        # So, no multiple write requests or write and read requests at the same time,
        # except the transitioning previous and next sharers

        # we need invalidation if the current state is MODIFIED
        if self._cache_state == CacheState.MODIFIED:
            # check sharer list
            sent = 0
            self._waiting_data_ok.clear()   # clear => we need data now
            for sharer in self._cache_sharer.keys():
                if sharer == requester:
                    continue
                async_handle = self._cache_sharer[sharer]
                if async_handle is not None:
                    async_handle.set()
                    sent += 1
            assert sent < 2, "There should be only one sharer for the CacheState.MODIFIED"
            print(f"Requester {requester[:16]} | Sent invalidation to {sent} sharers", flush=True)
            await self._waiting_data_ok.wait()

        # Check the existing sharer and initiate the invalidation
        if permission == CachePermission.WRITE:
            self._cache_state = CacheState.MODIFIED
        elif permission == CachePermission.READ:
            self._cache_state = CacheState.SHARED

        if requester not in self._cache_sharer.keys():
            self._cache_sharer[requester] = None

    async def transition(self, requester, permission: CachePermission):
        # TODO: Raise exception if permission is invalid
        # self.check_permission(requester, permission)

        if permission == CachePermission.READ or permission == CachePermission.WRITE:
            await self.process_fetch(requester, permission)
        elif permission == CachePermission.EVICT:
            self.process_evict(requester)

        print(f"Requester {requester[:16]} | Perm: {permission} | Cache state: {self._cache_state} | Sharers: {self._cache_sharer}", flush=True)
        return True

    async def install_invalidate_handle(self, requester):
        assert requester in self._cache_sharer.keys(), "Requester must be in the cache sharer list"
        # create asyncio event to trigger the invalidation
        async_handle = asyncio.Event()
        self._cache_sharer[requester] = async_handle

        # wait
        await async_handle.wait()

class RoyCacheLocalMSI(RoyCache):
    def __init__(self) -> None:
        super().__init__()

    def transition(self, permission: CachePermission):
        # TODO: complete the logic
        if permission == CachePermission.WRITE:
            self._cache_state = CacheState.MODIFIED
        elif permission == CachePermission.READ:
            self._cache_state = CacheState.SHARED
        elif permission == CachePermission.EVICT:
            self._cache_state = CacheState.INVALID

@ray.remote
class RoyProxy:
    def __init__(self, data, cache_class=RoyCacheDirMSI):
        self._data = data
        if cache_class:
            assert issubclass(cache_class, RoyCache), "cache_class must be a subclass of RoyCache"
            self._cache = cache_class()
        else:
            self._cache = None  # cache disabled

    def get_nocache(self):
        return self._data

    def set_nocache(self, data):
        self._data = data

    async def get(self, requester, permission=CachePermission.WRITE):
        if self._cache:
            await self._cache.transition(requester, permission)
        return self._data

    async def set(self, requester, data, permission=CachePermission.EVICT):
        '''
        Set the data and invalidate the cache
        '''
        self._data = data
        if self._cache:
            await self._cache.transition(requester, permission)

    async def install_invalidate_handle(self, requester):
        assert self._cache, "Cache must be enabled"
        await self._cache.install_invalidate_handle(requester)
        print(f"Requester {requester[:16]} | Invalidated", flush=True)

@ray.remote
class ActorTest:
    def __init__(self):
        pass

    def dummy_call(self):
        pass
