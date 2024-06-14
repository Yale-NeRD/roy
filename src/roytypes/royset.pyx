from cpython.pycapsule cimport PyCapsule_New
from cpython.exc cimport PyErr_NewException
from cpython.list cimport PyList_GetItem, PyList_Size
from libc.stdlib cimport malloc, free
from libc.time cimport clock, CLOCKS_PER_SEC
from cython.parallel import prange
import ray
from roytypes.roylock import RoyLock
from .royproxy import RoyProxy, gen_roy_id, RoyCacheLocalMSI, RoyCacheDirMSI, ActorTest
import time
import asyncio
from threading import Thread, Lock

cdef class RoyChunk:
    cdef object _ref  # underscore to indicate private attribute
    cdef object _cache  # underscore to indicate private attribute

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

cdef class RoySet:
    # data structure essentials
    cdef list chunk_ref_list # list of ray reference to each chunk
    cdef int num_buckets # size of each chunk, in # of elements
    cdef list chunk_list    # fetched chunk via ray.get or remote
    cdef int length # total length, not in chunks
    # locking support
    cdef object _lock
    cdef object _eviction_lock
    # configs
    cdef int per_chunk_lock
    # stats
    cdef double access_latency
    cdef int access_count
    cdef object _actor_test

    def __cinit__(self, int num_buckets=32, list value=None, object lock=None, int prefetch_idx=-1, int per_chunk_lock=0, list chunk_ref_list=None, int length=-1):
        '''
        @lock: lock object for synchronization. For deserialization, it should be given.
        @chunk_ref_list: list of ray reference to each chunk for deserializing
        '''
        if num_buckets <= 0:
            raise ValueError("Number of buckets must be greater than 0")
        if not ray.is_initialized():
            raise AssertionError(f"Ray must be initialized to use {self.__class__.__name__}")
        self.num_buckets = num_buckets

        if chunk_ref_list is not None:
            # likely deserialized in a new actor/worker
            assert length != -1
            self.chunk_ref_list = chunk_ref_list
            self.length = length
            # _actor_test = ActorTest.remote()
            # measure time of calling dummy_call
            # access_latency = 0
            # cnt = 0
            # for _ in range(10000):
            #     start = time.perf_counter_ns()
            #     ray.get(_actor_test.dummy_call.remote())
            #     access_latency += time.perf_counter_ns() - start
            #     cnt += 1
            # print(f"Access latency: {access_latency / cnt} ns", flush=True)
        else:
            # prepare buckets
            bucketized_sets = [set() for _ in range(num_buckets)]
            if value is not None:
                for item in value:  # work for any iterable (list, set, etc.)
                    bucketized_sets[hash(item) % num_buckets].add(item)
            self.chunk_ref_list = [RoyChunk(RoyProxy.remote(bucket, RoyCacheDirMSI), RoyCacheLocalMSI()) for bucket in bucketized_sets]
            self.length = len(value) if value else 0

        self.chunk_list = [None for _ in range(len(self.chunk_ref_list))]
        if lock is None:
            self._lock = RoyLock.remote()
        else:
            self._lock = lock
        self._eviction_lock = Lock()
        self.per_chunk_lock = per_chunk_lock
        self.access_latency = 0.0
        self.access_count = 0

        # Preload
        if prefetch_idx != -1:
            raise NotImplementedError("Prefetching is not implemented yet")
            # if not self.chunk_list[prefetch_idx]:
            #     proxy_ref = self.chunk_ref_list[prefetch_idx].ref
            #     chunk = ray.get(proxy_ref.get.remote(gen_roy_id()))
            #     self.chunk_list[prefetch_idx] = chunk

    def __contains__(self, object item):
        cdef int bucket_idx = hash(item) % self.num_buckets

        if self.chunk_list[bucket_idx] is None:
            self._fetch_chunk_(bucket_idx)

        return item in self.chunk_list[bucket_idx]

    def add(self, object item):
        cdef int bucket_idx = hash(item) % self.num_buckets
        print(f"Adding {item} | {hash(item)}", flush=True)

        if self.chunk_list[bucket_idx] is None:
            self._fetch_chunk_(bucket_idx)
        self.chunk_list[bucket_idx].add(item)

    # Define a function to invalidate the cache
    cdef void _invalidate_cache(self, proxy_ref, chunk_idx):
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

    @staticmethod
    def rebuild(chunk_ref_list, num_buckets, length, lock, prefetch_idx, per_chunk_lock):
        return RoySet(num_buckets, None, lock, prefetch_idx, per_chunk_lock, chunk_ref_list, length)

    def __reduce__(self):
        return (self.rebuild, (self.chunk_ref_list, self.num_buckets, self.length, self._lock, -1, self.per_chunk_lock))

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

    def __repr__(self):
        return f"RoySet({self.chunk_list})"
