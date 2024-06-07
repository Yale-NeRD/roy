from cpython.pycapsule cimport PyCapsule_New
from cpython.exc cimport PyErr_NewException
from cpython.list cimport PyList_GetItem, PyList_Size
from libc.stdlib cimport malloc, free
from libc.time cimport clock, CLOCKS_PER_SEC
from cython.parallel import prange
import ray

cdef class Roylist:
    cdef list chunk_ref_list
    cdef int chunk_size
    cdef int length
    cdef int num_chunks
    cdef list chunk_list
    cdef double access_latency
    cdef int access_count

    def __cinit__(self, list chunk_ref_list, int chunk_size, int length, int idx=-1):
        if chunk_ref_list is None:
            raise ValueError("Value cannot be None")
        if chunk_size <= 0:
            raise ValueError("Chunk size must be greater than 0")
        
        if not ray.is_initialized():
            raise AssertionError("Ray must be initialized")
        
        self.chunk_ref_list = chunk_ref_list
        self.chunk_size = chunk_size
        self.length = length
        self.num_chunks = len(chunk_ref_list)
        self.chunk_list = [[] for _ in range(self.num_chunks)]
        self.access_latency = 0.0
        self.access_count = 0

        # Preload
        if idx != -1:
            if not self.chunk_list[idx]:
                chunk = ray.get(self.chunk_ref_list[idx])
                self.chunk_list[idx] = chunk

    def __getitem__(self, int idx):
        if idx >= self.length:
            raise IndexError("Index out of range")

        cdef int chunk_idx = idx // self.chunk_size
        cdef int chunk_offset = idx % self.chunk_size

        if not self.chunk_list[chunk_idx]:
            self._fetch_chunk(chunk_idx)

        return self.chunk_list[chunk_idx][chunk_offset]

    cdef void _fetch_chunk(self, int chunk_idx):
        chunk = ray.get(self.chunk_ref_list[chunk_idx])
        self.chunk_list[chunk_idx] = chunk

    def get_access_latency(self):
        if self.access_count == 0:
            return 0.0
        return self.access_latency / self.access_count