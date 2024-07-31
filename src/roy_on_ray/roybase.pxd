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
    cdef object _local_lock
    cdef int length
    cdef int per_chunk_lock
    cdef object _roy_free_to_use
    cdef list _roy_inval_threads
    cdef object _roy_meta
    cdef object _roy_meta_ref

    # debugging Metadata
    cdef int _last_msg_time

    cdef void _init_new_chunk_list_(self, int num_chunks=*, object value=*)
    cdef void _fetch_chunk_(self, int chunk_idx)
    cdef void _evict_chunk_(self, int chunk_idx, int remove_data=*)
    # cdef void _flush_chunks_(self)
    cdef void _ensure_chunks_(self)

    # Metadata management
    cdef void _init_meta(self, int num_chunks)
    cdef void _fetch_and_update_meta(self)
    cdef void _evict_meta(self)