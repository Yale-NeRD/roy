from cpython.pycapsule cimport PyCapsule_New
from cpython.exc cimport PyErr_NewException
from cpython.list cimport PyList_GetItem, PyList_Size
# from libc.stdlib cimport malloc, free
# from libc.time cimport clock, CLOCKS_PER_SEC
from cython.parallel import prange
import ray
from roy_on_ray.roylock import RoyLock
from roy_on_ray.royproxy import RoyProxy, gen_roy_id, RoyCacheLocalMSI, RoyCacheDirMSI
from roy_on_ray.roybase cimport RoyBase, RoyChunk

cdef class RoySet(RoyBase):
    def __init__(self, int num_chunks=32, list value=None, object lock=None, int per_chunk_lock=0, list chunk_ref_list=None, object meta_ref=None, int length=-1):
        # TODO: length must be calculated from _meta.chunk_used or synchronized over RoyProxy
        '''
        @lock: lock object for synchronization. For deserialization, it should be given.
        @chunk_ref_list: list of ray reference to each chunk for deserializing
        '''
        super().__init__(num_chunks, value, lock, per_chunk_lock, chunk_ref_list, meta_ref, length)

    cdef void _init_new_chunk_list_(self, int num_chunks=32, object value=None):
        # prepare buckets
        bucketized_sets = [set() for _ in range(num_chunks)]
        if value is not None:
            assert isinstance(value, list) or isinstance(value, set), "Value must be a list or set"
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
        # print(f"Adding {item} | {hash(item)}", flush=True)

        if self.chunk_list[bucket_idx] is None:
            self._fetch_chunk_(bucket_idx)
        self.chunk_list[bucket_idx].add(item)

    def remove(self, object item):
        cdef int bucket_idx = hash(item) % self.num_chunks

        if self.chunk_list[bucket_idx] is None:
            self._fetch_chunk_(bucket_idx)
        self.chunk_list[bucket_idx].remove(item)

    @staticmethod
    def rebuild(chunk_ref_list, num_chunks, meta_ref, length, lock, per_chunk_lock):
        return RoySet(num_chunks, None, lock, per_chunk_lock, chunk_ref_list, meta_ref, length)

    def __reduce__(self):
        return (self.rebuild, (self.chunk_ref_list, self.num_chunks, self._roy_meta_ref, self.length, self._lock, self.per_chunk_lock))

    def __repr__(self):
        # merge all chunks into one set, except None
        return f"RoySet({set().union(*[chunk for chunk in self.chunk_list if chunk is not None])})"

    def __len__(self):
        self._ensure_chunks_()
        self.length = sum(len(chunk) for chunk in self.chunk_list if chunk is not None)
        return self.length
