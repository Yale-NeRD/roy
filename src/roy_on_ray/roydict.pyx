from cpython.pycapsule cimport PyCapsule_New
from cpython.exc cimport PyErr_NewException
from cpython.list cimport PyList_GetItem, PyList_Size
from libc.stdlib cimport malloc, free
from cython.parallel import prange
import ray
from roy_on_ray.roylock import RoyLock
from roy_on_ray.royproxy import RoyProxy, gen_roy_id, RoyCacheLocalMSI, RoyCacheDirMSI
from roy_on_ray.roybase cimport RoyBase, RoyChunk
import time

cdef class RoyDict(RoyBase):
    def __init__(self, dict value=None, int num_chunks=32, object lock=None, int per_chunk_lock=0, list chunk_ref_list=None, object meta_ref=None, int length=-1):
        super().__init__(num_chunks, value, lock, per_chunk_lock, chunk_ref_list, meta_ref, length)

    cdef void _init_new_chunk_list_(self, int num_chunks=32, object value=None):
        # Prepare buckets
        bucketized_dicts = [{} for _ in range(num_chunks)]
        if value is not None:
            if not isinstance(value, dict):
                print("Value is not None", flush=True)
                time.sleep(3)
                raise ValueError("Value must be a dict")

            for k, v in value.items():
                bucketized_dicts[hash(k) % num_chunks][k] = v
        self.chunk_ref_list = [RoyChunk(RoyProxy.remote(bucket, RoyCacheDirMSI), RoyCacheLocalMSI()) for bucket in bucketized_dicts]
        self.length = len(value) if value else 0

    def __getitem__(self, object key):
        cdef int bucket_idx = hash(key) % self.num_chunks
        if self.chunk_list[bucket_idx] is None:
            self._fetch_chunk_(bucket_idx)
        return self.chunk_list[bucket_idx][key]

    def __setitem__(self, object key, object value):
        cdef int bucket_idx = hash(key) % self.num_chunks
        if self.chunk_list[bucket_idx] is None:
            self._fetch_chunk_(bucket_idx)
        self.chunk_list[bucket_idx][key] = value

    def __delitem__(self, object key):
        cdef int bucket_idx = hash(key) % self.num_chunks
        if self.chunk_list[bucket_idx] is None:
            self._fetch_chunk_(bucket_idx)
        del self.chunk_list[bucket_idx][key]

    def keys(self):
        # It is expensive operation as it requires fetching all chunks
        keys = []
        self._ensure_chunks_()
        for chunk in self.chunk_list:
            assert chunk is not None, "Chunk must not be None, as it must be fetched first"
            keys.extend(chunk.keys())
        return keys

    def values(self):
        values = []
        self._ensure_chunks_()
        for chunk in self.chunk_list:
            assert chunk is not None, "Chunk must not be None, as it must be fetched first"
            values.extend(chunk.values())
        return values

    def items(self):
        items = []
        self._ensure_chunks_()
        for chunk in self.chunk_list:
            assert chunk is not None, "Chunk must not be None, as it must be fetched first"
            items.extend(chunk.items())
        return items

    def __len__(self):
        # TODO: cache the length dynamically
        self._ensure_chunks_()
        return sum([len(chunk) for chunk in self.chunk_list])

    def __contains__(self, object key):
        cdef int bucket_idx = hash(key) % self.num_chunks
        if self.chunk_list[bucket_idx] is None:
            self._fetch_chunk_(bucket_idx)
        return key in self.chunk_list[bucket_idx]

    def clear(self):
        # Flush any items in the cache
        self._ensure_chunks_()
        for idx, chunk in enumerate(self.chunk_list):
            # Clear the chunk and write back
            chunk.clear()
            # self._evict_chunk_(idx)   # Make it lazy eviction (at release time)
        # Reset the meta data
        self.length = 0

    @staticmethod
    def rebuild(chunk_ref_list, num_chunks, meta_ref, length, lock, per_chunk_lock):
        return RoyDict(None, num_chunks, lock, per_chunk_lock, chunk_ref_list, meta_ref, length)

    def __reduce__(self):
        return (self.rebuild, (self.chunk_ref_list, self.num_chunks, self._roy_meta_ref, self.length, self._lock, self.per_chunk_lock))

    def __repr__(self):
        '''
        This function only prints the currently fetched chunks. It does not fetch all chunks.
        To see the full list, use `items()` and print them individually
        '''
        return f"RoyDict({self.items()})"
