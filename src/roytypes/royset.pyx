from cpython.pycapsule cimport PyCapsule_New
from cpython.exc cimport PyErr_NewException
from cpython.list cimport PyList_GetItem, PyList_Size
from libc.stdlib cimport malloc, free
from libc.time cimport clock, CLOCKS_PER_SEC
from cython.parallel import prange
import ray
from roytypes.roylock import RoyLock
from roytypes.royproxy import RoyProxy, gen_roy_id, RoyCacheLocalMSI, RoyCacheDirMSI, ActorTest
from roytypes.roybase cimport RoyBase, RoyChunk

cdef class RoySet(RoyBase):
    # stats
    # cdef double access_latency
    # cdef int access_count
    # cdef object _actor_test

    def __init__(self, int num_chunks=32, list value=None, object lock=None, int prefetch_idx=-1, int per_chunk_lock=0, list chunk_ref_list=None, int length=-1):
        '''
        @lock: lock object for synchronization. For deserialization, it should be given.
        @chunk_ref_list: list of ray reference to each chunk for deserializing
        '''
        super().__init__(num_chunks, value, lock, per_chunk_lock, chunk_ref_list, length)

        # Preload
        if prefetch_idx != -1:
            raise NotImplementedError("Prefetching is not implemented yet")
            # if not self.chunk_list[prefetch_idx]:
            #     proxy_ref = self.chunk_ref_list[prefetch_idx].ref
            #     chunk = ray.get(proxy_ref.get.remote(gen_roy_id()))
            #     self.chunk_list[prefetch_idx] = chunk

    cdef void _init_new_chunk_list_(self, int num_chunks=32, list value=None):
        # prepare buckets
        bucketized_sets = [set() for _ in range(num_chunks)]
        if value is not None:
            for item in value:  # work for any iterable (list, set, etc.)
                bucketized_sets[hash(item) % num_chunks].add(item)
        self.chunk_ref_list = [RoyChunk(RoyProxy.remote(bucket, RoyCacheDirMSI), RoyCacheLocalMSI()) for bucket in bucketized_sets]
        self.length = len(value) if value else 0

    def __contains__(self, object item):
        cdef int bucket_idx = hash(item) % self.num_chunks

        if self.chunk_list[bucket_idx] is None:
            self._fetch_chunk_(bucket_idx)

        return item in self.chunk_list[bucket_idx]

    def add(self, object item):
        cdef int bucket_idx = hash(item) % self.num_chunks
        print(f"Adding {item} | {hash(item)}", flush=True)

        if self.chunk_list[bucket_idx] is None:
            self._fetch_chunk_(bucket_idx)
        self.chunk_list[bucket_idx].add(item)

    @staticmethod
    def rebuild(chunk_ref_list, num_chunks, length, lock, prefetch_idx, per_chunk_lock):
        return RoySet(num_chunks, None, lock, prefetch_idx, per_chunk_lock, chunk_ref_list, length)

    def __reduce__(self):
        return (self.rebuild, (self.chunk_ref_list, self.num_chunks, self.length, self._lock, -1, self.per_chunk_lock))
    def __repr__(self):
        return f"RoySet({self.chunk_list})"
