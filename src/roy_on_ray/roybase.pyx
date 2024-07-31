from cpython.pycapsule cimport PyCapsule_New
from cpython.exc cimport PyErr_NewException
from cpython.list cimport PyList_GetItem, PyList_Size
from libc.stdlib cimport malloc, free
from libc.time cimport clock, CLOCKS_PER_SEC
from cython.parallel import prange
import ray
from roy_on_ray.roylock import RoyLock
from roy_on_ray.royproxy import RoyProxy, gen_roy_id, RoyCacheLocalMSI, RoyCacheDirMSI
import time
from asyncio import Event
import threading
from threading import Thread, Lock

class RoyMeta:
    def __init__(self, int num_chunks):
        self.chunk_versions = [0 for _ in range(num_chunks)]

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

    def __init__(self, int num_chunks=4, object value=None, object lock=None, int per_chunk_lock=0, list chunk_ref_list=None, object meta_ref=None, int length=-1):
        '''
        @lock: lock object for synchronization. For deserialization, it should be given.
        @chunk_ref_list: list of ray reference to each chunk for deserializing
        '''
        # TODO: include chunk_ref_list into meta_ref (we can get it from remote only once at the beginning
        # and keep the local version separately because self.chunk_ref_list is read-only anyway)
        if num_chunks <= 0:
            raise ValueError("Number of buckets must be greater than 0")
        if not ray.is_initialized():
            print(f"Ray must be initialized to use {self.__class__.__name__}", flush=True)
            time.sleep(3)
            raise AssertionError(f"Ray must be initialized to use {self.__class__.__name__}")
        self.num_chunks = num_chunks

        if meta_ref is None:
            self._init_meta(num_chunks)
        else:
            self._roy_meta_ref = meta_ref

        if chunk_ref_list is not None:
            # likely deserialized in a new actor/worker
            assert length != -1
            self.chunk_ref_list = chunk_ref_list
            self.length = length
        else:
            # Call the subclass method to initialize chunk_ref_list
            self._init_new_chunk_list_(num_chunks, value)
            assert self.chunk_ref_list is not None

        # TODO: replace chunk_list with self.chunk_ref_list.cache
        self.chunk_list = [None for _ in range(len(self.chunk_ref_list))]
        if lock is None:
            self._lock = RoyLock.remote()
        else:
            self._lock = lock
        self._local_lock = Lock()
        self.per_chunk_lock = per_chunk_lock
        self._roy_free_to_use = Event()
        self._roy_free_to_use.set()  # Initially, not in use
        self._roy_inval_threads = [None for _ in range(len(self.chunk_ref_list))]
        # debugging meta
        _last_msg_time = time.time()

    cdef void _init_meta(self, int num_chunks):
        self._roy_meta = RoyMeta(num_chunks)
        self._roy_meta_ref = RoyProxy.remote(
                self._roy_meta, cache_class=None)

    cdef void _fetch_and_update_meta(self):
        assert self._roy_meta_ref is not None, "Metadata reference must be initialized"
        new_meta = ray.get(self._roy_meta_ref.get_nocache.remote())
        # specific logic to compare local and remote version
        if self._roy_meta is None:
            self._roy_meta = new_meta
            return

        cdef int stale_entries = 0
        cdef int cached_entries = 0
        for chunk_idx in range(self.num_chunks):
            if self.chunk_list[chunk_idx] is not None:
                cached_entries += 1
            if new_meta.chunk_versions[chunk_idx] > self._roy_meta.chunk_versions[chunk_idx]:
                if self.chunk_list[chunk_idx] is not None:
                    stale_entries += 1
                # give up the local data; reference should be the same
                self.chunk_list[chunk_idx] = None
        self._roy_meta = new_meta

    cdef void _ensure_chunks_(self):
        for i in range(self.num_chunks):
            if self.chunk_list[i] is None:
                self._fetch_chunk_(i)
            # print(f"Stale entries: {stale_entries} / {cached_entries}", flush=True)

    cdef void _evict_meta(self):
        assert self._roy_meta_ref is not None, "Metadata reference must be initialized"
        ray.get(self._roy_meta_ref.set_nocache.remote(self._roy_meta))

    cdef void _init_new_chunk_list_(self, int num_chunks=32, object value=None):
        raise NotImplementedError("This method should be implemented in the subclass")

    cdef void _fetch_chunk_(self, int chunk_idx):
        # timeout = 3
        # if self._roy_inval_threads[chunk_idx] is not None:
        #     self._roy_inval_threads[chunk_idx].join()
        assert self.chunk_list[chunk_idx] is None, "Chunk must be None to fetch"
        assert self.chunk_ref_list[chunk_idx] is not None, "Chunk reference must be initialized"
        assert self._roy_meta is not None, "Metadata must be initialized/fetched"
        proxy_ref = self.chunk_ref_list[chunk_idx].ref
        # TODO: fault tolerance for actor termination
        self.chunk_list[chunk_idx] = ray.get(proxy_ref.get.remote(gen_roy_id()))
        # print(f"Fetched chunk {chunk_idx}", flush=True)
        self._roy_meta.chunk_versions[chunk_idx] += 1

    cdef void _evict_chunk_(self, int chunk_idx, int remove_data=False):
        if self.chunk_list[chunk_idx] is None:
            return
        proxy_ref = self.chunk_ref_list[chunk_idx].ref
        data = self.chunk_list[chunk_idx]
        if remove_data:
            self.chunk_list[chunk_idx] = None
        try:
            # print(f"Evicting chunk {chunk_idx}", flush=True)
            ray.get(proxy_ref.set.remote(gen_roy_id(), data))
        except Exception as e:
            #print exception type
            if self._last_msg_time + 1 < time.time():
                print(f"Exception for evicting chunk {chunk_idx}: {e.__class__.__name__} :: {e}", flush=True)
                self._last_msg_time = time.time()

    def __lock__(self):
        # print(f"Locking...{self.__class__.__name__}", flush=True)
        self._local_lock.acquire()
        # print(f"Locked: {self._local_lock}", flush=True)
        if self._lock is not None:
            ray.get(self._lock.lock.remote())
        self._fetch_and_update_meta()
        # print(f"Locked and fetched meta: {self._lock}", flush=True)

    def _flush_chunks_(self):
        # remove all chunk_list
        for chunk_idx, _ in enumerate(self.chunk_list):
            if self.chunk_list[chunk_idx] is not None:
                # print(f"Evicting chunk {chunk_idx}", flush=True)
                self._evict_chunk_(chunk_idx)
                # print(f"Evicted chunk {chunk_idx}", flush=True)

    def __unlock__(self, cache=True):
        # print(f"Unlocking...{self.__class__.__name__}", flush=True)
        self._flush_chunks_()
        self._evict_meta()
        if self._lock is not None:
            ray.get(self._lock.unlock.remote())
        # print(f"Unlocked: {self._lock}", flush=True)
        self._local_lock.release()
        # print(f"Released: {self._local_lock}", flush=True)

    def flush(self):
        for chunk_idx, _ in enumerate(self.chunk_list):
            if self.chunk_list[chunk_idx] is not None:
                # print(f"FLUSH: Evicting chunk {chunk_idx}", flush=True)
                self._evict_chunk_(chunk_idx)
                # print(f"FLUSH: Evicted chunk {chunk_idx}", flush=True)

    def __enter__(self):
        self.__lock__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.__unlock__()

    def __del__(self):
        self._flush_chunks_()
        # join all threads
        for thread in self._roy_inval_threads:
            if thread is not None and thread != threading.current_thread():
                thread.join()
