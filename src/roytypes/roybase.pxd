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
    cdef object _ref
    cdef object _cache

cdef class RoyBase:
    cdef list chunk_ref_list
    cdef list chunk_list
    cdef int num_chunks
    cdef object _lock
    cdef object _eviction_lock
    cdef int length
    cdef int per_chunk_lock
    cdef object _roy_in_use
    cdef list _roy_inval_threads

    cdef void _init_new_chunk_list_(self, int num_chunks=*, list value=*)
    cdef void _invalidate_cache(self, object proxy_ref, int chunk_idx, int timeout)
    cdef void _fetch_chunk_(self, int chunk_idx)
    cdef void _evict_chunk_(self, int chunk_idx)
    # cdef void _flush_chunks_(self)