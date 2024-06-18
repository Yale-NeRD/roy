from cpython.pycapsule cimport PyCapsule_New
from cpython.exc cimport PyErr_NewException
from cpython.list cimport PyList_GetItem, PyList_Size
from libc.stdlib cimport malloc, free
from libc.time cimport clock, CLOCKS_PER_SEC
from cython.parallel import prange
import ray
from roytypes.roylock import RoyLock
from roytypes.royproxy import RoyProxy, gen_roy_id, RoyCacheLocalMSI, RoyCacheDirMSI, ActorTest
import time
import asyncio
from threading import Thread, Lock

cdef class RoyChunk:
    # == variables: relocated to .pxd ==

    def __cinit__(self, object ref, object cache):
        self._ref = ref
        self._cache = cache

    @property
    def ref(self):
        return self._ref

    @ref.setter
    def ref(self, value):
        self._ref = value

    @property
    def cache(self):
        return self._cache

    @cache.setter
    def cache(self, value):
        self._cache = value

    def __reduce__(self):
        return (self.rebuild, (self._ref, self._cache))

    @staticmethod
    def rebuild(ref, cache):
        return RoyChunk(ref, cache)

cdef class RoyBase:
    # == variables: relocated to .pxd ==

    def __init__(self, int num_chunks=32, list value=None, object lock=None, int per_chunk_lock=0, list chunk_ref_list=None, int length=-1):
        '''
        @lock: lock object for synchronization. For deserialization, it should be given.
        @chunk_ref_list: list of ray reference to each chunk for deserializing
        '''
        if num_chunks <= 0:
            raise ValueError("Number of buckets must be greater than 0")
        if not ray.is_initialized():
            raise AssertionError(f"Ray must be initialized to use {self.__class__.__name__}")
        self.num_chunks = num_chunks

        if chunk_ref_list is not None:
            # likely deserialized in a new actor/worker
            assert length != -1
            self.chunk_ref_list = chunk_ref_list
            self.length = length
        else:
            self._init_new_chunk_list_(num_chunks, value)
            assert self.chunk_ref_list is not None

        self.chunk_list = [None for _ in range(len(self.chunk_ref_list))]
        if lock is None:
            self._lock = RoyLock.remote()
        else:
            self._lock = lock
        self._eviction_lock = Lock()
        self.per_chunk_lock = per_chunk_lock

    cdef void _init_new_chunk_list_(self, int num_chunks=32, list value=None):
        raise NotImplementedError("This method should be implemented in the subclass")

    # Define a function to invalidate the cache
    cdef void _invalidate_cache(self, object proxy_ref, int chunk_idx):
        print(f"Waiting for invalidation signal for chunk {chunk_idx}", flush=True)
        # wait for the signal that the cache needs to be invalidated
        ray.get(proxy_ref.install_invalidate_handle.remote(gen_roy_id()))
        # invalidate the cache if it haven't
        # - it might be already invalidated by _evict_chunk_
        if self.chunk_list[chunk_idx] is not None:
            print(f"Invalidating cache for chunk {chunk_idx}", flush=True)
            self._evict_chunk_(chunk_idx)

    cdef void _fetch_chunk_(self, int chunk_idx):
        proxy_ref = self.chunk_ref_list[chunk_idx].ref
        self.chunk_list[chunk_idx] = ray.get(proxy_ref.get.remote(gen_roy_id()))
        
        thread = Thread(target=self._invalidate_cache, args=(proxy_ref, chunk_idx))
        thread.start()

    cdef void _evict_chunk_(self, int chunk_idx):
        with self._eviction_lock:
            if self.chunk_list[chunk_idx] is None:
                return
            proxy_ref = self.chunk_ref_list[chunk_idx].ref
            data = self.chunk_list[chunk_idx]
            self.chunk_list[chunk_idx] = None
            ray.get(proxy_ref.set.remote(gen_roy_id(), data))

    def __lock__(self):
        if self._lock is not None:
            ray.get(self._lock.lock.remote())

    def __unlock__(self, cache=True):
        if not cache:
            # remove all chunk_list
            for chunk_idx, _ in enumerate(self.chunk_list):
                if self.chunk_list[chunk_idx] is not None:
                    self._evict_chunk_(chunk_idx)
                    print(f"Evicting chunk {chunk_idx}", flush=True)

        if self._lock is not None:
            ray.get(self._lock.unlock.remote())

    def __enter__(self):
        self.__lock__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.__unlock__()
