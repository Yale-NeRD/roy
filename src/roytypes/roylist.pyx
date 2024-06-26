from cpython.pycapsule cimport PyCapsule_New
from cpython.exc cimport PyErr_NewException
from cpython.list cimport PyList_GetItem, PyList_Size
from libc.stdlib cimport malloc, free
from cython.parallel import prange
import ray
from roytypes.roylock import RoyLock
from roytypes.royproxy import RoyProxy, gen_roy_id, RoyCacheLocalMSI, RoyCacheDirMSI, ActorTest
from roytypes.roybase cimport RoyBase, RoyChunk

cdef class ListChunkMeta:
    cdef object last_used_chunk # Ray ref to the index of the last chunk in use
    cdef int max_element_per_chunk
    cdef object chunk_used # Ray ref to the list of element counts for each chunk

    def __init__(self, object last_used_chunk=None, int max_element_per_chunk=1024, object chunk_used=None):
        self.last_used_chunk = last_used_chunk
        self.max_element_per_chunk = max_element_per_chunk
        self.chunk_used = chunk_used

cdef class RoyList(RoyBase):
    cdef ListChunkMeta _meta

    def __init__(self, int num_chunks=32, list value=None, object lock=None, int per_chunk_lock=0, list chunk_ref_list=None, int length=-1, ListChunkMeta meta=ListChunkMeta()):
        # TODO: length must be calculated from _meta.chunk_used or synchronized over RoyProxy
        '''
        @lock: lock object for synchronization. For deserialization, it should be given.
        @chunk_ref_list: list of ray reference to each chunk for deserializing
        '''
        super().__init__(num_chunks, value, lock, per_chunk_lock, chunk_ref_list, length)
        # if value is not None:
        #     self._init_new_chunk_list_(num_chunks, value)
        self._meta = meta
        if chunk_ref_list is None:
            # create the used chunk list based on the initial value (can be even 0 elements)
            # we create RoyProxy with caching disabled
            self._meta.chunk_used = RoyProxy.remote([len(chunk) if chunk else 0 for chunk in self.chunk_list], None)
            self._meta.last_used_chunk = RoyProxy.remote(0, None)

    cdef void _init_new_chunk_list_(self, int num_chunks=32, list value=None):
        '''
        Called in super().__init__ to initialize the chunk list
        '''
        if value is None:
            chunked_lists = [[] for _ in range(num_chunks)]
        else:
            chunk_size = (len(value) + num_chunks - 1) // num_chunks  # calculate the size of each chunk
            chunked_lists = [value[i*chunk_size:(i+1)*chunk_size] for i in range(num_chunks)]
        self.chunk_ref_list = [RoyChunk(RoyProxy.remote(chunk, RoyCacheDirMSI), RoyCacheLocalMSI()) for chunk in chunked_lists]
        self.length = len(value) if value else 0

    def __getitem__(self, int index):
        if index < 0 or index >= self.length:
            raise IndexError("list index out of range")
        chunk_used = ray.get(self._meta.chunk_used.get_nocache.remote())
        cdef int chunk_idx = 0
        cdef int intra_chunk_idx = 0
        for i in range(self.num_chunks):
            ray.get(chunk_used[i])
            if index < chunk_used[i]:
                chunk_idx = i
                break
            index -= chunk_used[i]
        if self.chunk_list[chunk_idx] is None:
            self._fetch_chunk_(chunk_idx)
        return self.chunk_list[chunk_idx][index]

    def __setitem__(self, int index, object value):
        if index < 0 or index >= self.length:
            raise IndexError("list index out of range")
        cdef list chunk_used = ray.get(self._meta.chunk_used.get_nocache.remote())
        cdef int chunk_idx = 0
        cdef int intra_chunk_idx = 0
        for i in range(self.num_chunks):
            if index < chunk_used[i]:
                chunk_idx = i
                break
            index -= chunk_used[i]
        if chunk_idx >= self.num_chunks:
            raise IndexError("list index out of range")
        if self.chunk_list[chunk_idx] is None:
            self._fetch_chunk_(chunk_idx)
        self.chunk_list[chunk_idx][index] = value

    def append(self, object item):
        cdef int chunk_idx = ray.get(self._meta.last_used_chunk.get_nocache.remote())
        cdef list chunk_used = ray.get(self._meta.chunk_used.get_nocache.remote())

        while chunk_idx < self.num_chunks and chunk_used[chunk_idx] >= self._meta.max_element_per_chunk:
            chunk_idx += 1
        if chunk_idx >= self.num_chunks:
            raise OverflowError("Exceeded maximum number of chunks")
        if self.chunk_list[chunk_idx] is None:
            self._fetch_chunk_(chunk_idx)

        self.chunk_list[chunk_idx].append(item)
        chunk_used[chunk_idx] += 1
        ray.get(self._meta.chunk_used.set_nocache.remote(chunk_used))
        ray.get(self._meta.last_used_chunk.set_nocache.remote(chunk_idx))
        self.length += 1

    def extend(self, object items):
        for item in items:
            self.append(item)

    def insert(self, int index, object item):
        if index < 0:
            index = self.length + index
        if index > self.length:
            raise IndexError("list index out of range")

        self.append(None)  # Increase length by 1 to make space

        for i in range(self.length-1, index, -1):
            self[i] = self[i-1]

        self[index] = item

    def remove(self, object item):
        index = self.index(item)
        self.pop(index)

    def pop(self, int index=-1):
        if index < 0:
            index = self.length + index
        if index >= self.length or index < 0:
            raise IndexError("pop index out of range")

        item = self[index]
        for i in range(index, self.length-1):
            self[i] = self[i+1]

        self.length -= 1
        return item

    def clear(self):
        # TODO: flush any items in the cache
        self.chunk_list = [None] * self.num_chunks
        self.chunk_ref_list = [None] * self.num_chunks
        self.length = 0
        self._meta.last_used_chunk = 0

    def index(self, object item, int start=0, int end=-1):
        # TODO: compute end based on updated length
        # if end == -1:
        #     end = self.length

        cdef int chunk_idx = ray.get(self._meta.last_used_chunk.get_nocache.remote())
        cdef list chunk_used = ray.get(self._meta.chunk_used.get_nocache.remote())
        cdef int item_idx = 0
        for i in range(start, chunk_idx+1):
            if self.chunk_list[i] is None:
                self._fetch_chunk_(i)
            if item in self.chunk_list[i]:
                return item_idx + self.chunk_list[i].index(item)
            item_idx += chunk_used[i]
        raise ValueError(f"{item} is not in list")

    def __len__(self):
        return self.length

    def __contains__(self, object item):
        try:
            self.index(item)
            return True
        except ValueError:
            return False

    def __iter__(self):
        for i in range(self.length):
            yield self[i]

    def __reduce__(self):
        return (self.rebuild, (self.chunk_ref_list, self.num_chunks, self.length, self._lock, self.per_chunk_lock, self._meta))

    @staticmethod
    def rebuild(chunk_ref_list, num_chunks, length, lock, per_chunk_lock, meta):
        return RoyList(num_chunks, None, lock, per_chunk_lock, chunk_ref_list, length, meta)

    def __repr__(self):
        return f"RoyList({self.chunk_list})"
    