from cpython.pycapsule cimport PyCapsule_New
from cpython.exc cimport PyErr_NewException
from cpython.list cimport PyList_GetItem, PyList_Size
from libc.stdlib cimport malloc, free
from libc.time cimport clock, CLOCKS_PER_SEC
from cython.parallel import prange
import ray
from roytypes.roylock import RoyLock

cdef class RoyList:
    # data structure essentials
    cdef list chunk_ref_list # list of ray reference to each chunk
    cdef int chunk_size # size of each chunk, in # of elements
    cdef list chunk_list    # fetched chunk via ray.get or remote
    cdef int length # total length, not in chunks
    # locking support
    cdef object _lock
    # configs
    cdef int per_chunk_lock
    # stats
    cdef double access_latency
    cdef int access_count


    def __cinit__(self, list value, int chunk_size, object lock=None, int prefetch_idx=-1, int per_chunk_lock=0, list chunk_ref_list=None, int length=-1):
        '''
        @lock: lock object for synchronization. For deserialization, it should be given.
        @chunk_ref_list: list of ray reference to each chunk for deserializing
        '''
        if value is None and chunk_ref_list is None:
            raise ValueError("Value cannot be None")
        if chunk_size <= 0:
            raise ValueError("Chunk size must be greater than 0")
        if not ray.is_initialized():
            raise AssertionError("Ray must be initialized")

        if chunk_ref_list is not None:
            assert length != -1
            self.chunk_ref_list = chunk_ref_list
            self.length = length
        else:
            self.chunk_ref_list = [ray.put(value[i:i + chunk_size]) for i in range(0, len(value), chunk_size)]
            self.length = len(value)
        self.chunk_size = chunk_size
        self.chunk_list = [[] for _ in range(len(self.chunk_ref_list))]
        if lock is None:
            self._lock = RoyLock.remote()
        else:
            self._lock = lock
        self.per_chunk_lock = per_chunk_lock
        self.access_latency = 0.0
        self.access_count = 0

        # Preload
        if prefetch_idx != -1:
            if not self.chunk_list[prefetch_idx]:
                chunk = ray.get(self.chunk_ref_list[prefetch_idx])
                self.chunk_list[prefetch_idx] = chunk

    def __getitem__(self, int idx):
        if idx >= self.length:
            raise IndexError("Index out of range")

        cdef int chunk_idx = idx // self.chunk_size
        cdef int chunk_offset = idx % self.chunk_size

        if not self.chunk_list[chunk_idx]:
            self._fetch_chunk_(chunk_idx)

        return self.chunk_list[chunk_idx][chunk_offset]

    cdef void _fetch_chunk_(self, int chunk_idx):
        chunk = ray.get(self.chunk_ref_list[chunk_idx])
        self.chunk_list[chunk_idx] = chunk

    @staticmethod
    def rebuild(chunk_ref_list, chunk_size, length, lock, prefetch_idx, per_chunk_lock):
        return RoyList(None, chunk_size, lock, prefetch_idx, per_chunk_lock, chunk_ref_list, length)

    def __reduce__(self):
        return (self.rebuild, (self.chunk_ref_list, self.chunk_size, self.length, self._lock, -1, self.per_chunk_lock))

    def __lock__(self):
        if self._lock is not None:
            ray.get(self._lock.lock.remote())

    def __unlock__(self):
        if self._lock is not None:
            ray.get(self._lock.unlock.remote())

    def __enter__(self):
        self.__lock__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.__unlock__()

    '''
    @classmethod
    def reconstruct(cls, chunk_ref_list, chunk_size, length, idx):
        obj = cls.__new__(cls)  # create a new instance without calling __init__
        obj.chunk_ref_list = chunk_ref_list
        obj.chunk_size = chunk_size
        obj.length = length
        obj.num_chunks = len(chunk_ref_list)
        obj.chunk_list = [[] for _ in range(obj.num_chunks)]
        obj.access_latency = 0.0
        obj.access_count = 0

        # Preload
        if idx != -1:
            if not obj.chunk_list[idx]:
                chunk = ray.get(obj.chunk_ref_list[idx])
                obj.chunk_list[idx] = chunk

        return obj

    def get_access_latency(self):
        if self.access_count == 0:
            return 0.0
        return self.access_latency / self.access_count
    '''
