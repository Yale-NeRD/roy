import ray
import asyncio
from enum import Enum
from typing import Annotated

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
    '''
    def __init__(self, 
        requester: Annotated[str, "ray id or handle of the requester actor"],
        invalidate_handle: Annotated[asyncio.Event, "the event to trigger the invalidation"]=None
        ):
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
            # Now the invalidation is deprecated and replaced with eviction during lock release
            assert_msg = "\033[91m** Make sure that all accesses are within lock scope.\n"
            assert_msg += "Roy Error:: Accessing (potentially) stale data.\033[0m"
            assert False, assert_msg

        # Check the existing sharer and initiate the invalidation
        if permission == CachePermission.WRITE:
            self._cache_state = CacheState.MODIFIED
        elif permission == CachePermission.READ:
            self._cache_state = CacheState.SHARED

        if requester not in self._cache_sharer.keys():
            self._cache_sharer[requester] = None

    async def transition(self, requester, permission: CachePermission):
        # TODO: Raise exception if permission is invalid

        if permission == CachePermission.READ or permission == CachePermission.WRITE:
            await self.process_fetch(requester, permission)
        elif permission == CachePermission.EVICT:
            self.process_evict(requester)

        # print(f"Requester {requester[:16]} | Perm: {permission} | Cache state: {self._cache_state} | Sharers: {self._cache_sharer}", flush=True)
        return True

    async def install_invalidate_handle(self, requester, timeout):
        '''
        @return: bool - True if the invalidation is required to the requester (or already done),
                        False if it is timed out (requester can keep it for now, but must check again later)
        '''
        if requester not in self._cache_sharer.keys():
            return  # requester might already invalidate the data
        # assert requester in self._cache_sharer.keys(), f"Requester must be in the cache sharer list: {requester} not in {self._cache_sharer.keys()}"

        # create asyncio event to trigger the invalidation
        async_handle = asyncio.Event()
        self._cache_sharer[requester] = async_handle

        # wait
        await async_handle.wait()

    def _clean_up_(self):
        # system is likely terminating - clear the cache sharer
        for sharer in self._cache_sharer.keys():
            async_handle = self._cache_sharer[sharer]
            if async_handle:
                async_handle.set()
            print(f"TERM | Sharer {sharer[:16]} | Invalidated", flush=True)
        while len(self._cache_sharer) > 0:
            # wait for 1 sec
            asyncio.sleep(1)

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

    async def get(self, requester, permission=CachePermission.WRITE, verbose=False):
        if self._cache:
            await self._cache.transition(requester, permission)
        # print the amount of data
        if verbose:
            try:
                print(f"FETCH: Requester {requester[:16]} | Data size: {len(self._data)}", flush=True)
            except Exception as e:
                print(f"Error occurred: {e}", flush=True)
        return self._data

    async def set(self, requester, data, permission=CachePermission.EVICT, verbose=False):
        '''
        Set the data and invalidate the cache
        '''
        self._data = data
        if self._cache:
            await self._cache.transition(requester, permission)
        # print the amount of data
        if verbose:
            try:
                print(f"EVICT: Requester {requester[:16]} | Data size: {len(data)}", flush=True)
            except Exception as e:
                print(f"Error occurred: {e}", flush=True)

    async def install_invalidate_handle(self, requester, timeout=3):
        assert self._cache, "Cache must be enabled"
        await self._cache.install_invalidate_handle(requester, timeout)
        print(f"Requester {requester[:16]} | Invalidated", flush=True)

    def __del__(self):
        print(f"RoyProxy {self} is deleted", flush=True)
        if self._cache:
            self._cache._clean_up_()
