from cpython.pycapsule cimport PyCapsule_New
from cpython.exc cimport PyErr_NewException
from cpython.list cimport PyList_GetItem, PyList_Size
from libc.stdlib cimport malloc, free
from cython.parallel import prange
import ray
from roy_on_ray.roylock import RoyLock
from roy_on_ray.royproxy import RoyProxy, gen_roy_id, RoyCacheLocalMSI, RoyCacheDirMSI
from roy_on_ray.roybase cimport RoyBase, RoyChunk

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

    def __init__(self, int num_chunks=32, list value=None, object lock=None, int per_chunk_lock=0, list chunk_ref_list=None, object meta_ref=None, int length=-1, ListChunkMeta meta=ListChunkMeta()):
        # TODO: length must be calculated from _meta.chunk_used or synchronized over RoyProxy
        '''
        @lock: lock object for synchronization. For deserialization, it should be given.
        @chunk_ref_list: list of ray reference to each chunk for deserializing
        '''
        super().__init__(num_chunks, value, lock, per_chunk_lock, chunk_ref_list, meta_ref, length)
        # if value is not None:
        #     self._init_new_chunk_list_(num_chunks, value)
        self._meta = meta
        if chunk_ref_list is None:
            # create the used chunk list based on the initial value (can be even 0 elements)
            # we create RoyProxy with caching disabled
            self._meta.chunk_used = RoyProxy.remote(
                [len(chunk) if chunk else 0 for chunk in self.chunk_list],
                cache_class=None)
            self._meta.last_used_chunk = RoyProxy.remote(0, None)

    cdef void _init_new_chunk_list_(self, int num_chunks=32, object value=None):
        '''
        Called in super().__init__ to initialize the chunk list
        '''
        if value is None:
            chunked_lists = [[] for _ in range(num_chunks)]
        else:
            assert isinstance(value, list), "Value must be a list"
            # chunk_size = (len(value) + num_chunks - 1) // num_chunks  # calculate the size of each chunk
            chunk_size = self._meta.max_element_per_chunk
            chunked_lists = [value[i*chunk_size:(i+1)*chunk_size] for i in range(num_chunks)]
        self.chunk_ref_list = [RoyChunk(RoyProxy.remote(chunk, RoyCacheDirMSI), RoyCacheLocalMSI()) for chunk in chunked_lists]
        self.length = len(value) if value else 0
        # print(f"Initial chunked list: {chunked_lists}")

    def __getitem__(self, int index):
        cdef list chunk_used = self._fetch_chunk_usage_and_length(index)
        cdef int chunk_idx = 0
        cdef int intra_chunk_idx = 0
        for i in range(self.num_chunks):
            if index < chunk_used[i]:
                chunk_idx = i
                break
            index -= chunk_used[i]
        if self.chunk_list[chunk_idx] is None:
            self._fetch_chunk_(chunk_idx)
        # print(f"Fetching chunk {chunk_idx} for index {index}", flush=True)
        return self.chunk_list[chunk_idx][index]

    def __setitem__(self, int index, object value):
        cdef list chunk_used = self._fetch_chunk_usage_and_length(index)
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

    def __len__(self):
        return sum(ray.get(self._meta.chunk_used.get_nocache.remote()))

    def _fetch_chunk_usage_and_length(self, int index) -> list:
        cdef list chunk_used = ray.get(self._meta.chunk_used.get_nocache.remote())
        self.length  = sum(chunk_used)
        if index >= 0 and index >= self.length:
            raise IndexError("list index out of range")
        return chunk_used

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
        cdef list chunk_used = self._fetch_chunk_usage_and_length(index)
        cdef int chunk_last_used = ray.get(self._meta.last_used_chunk.get_nocache.remote())
        cdef int chunk_idx = -1
        cdef int chunk_item_idx = 0
        if index < 0:
            index = self.length + index
        if index > self.length:
            raise IndexError("list index out of range")

        # find chunk and item index
        for i in range(chunk_last_used):
            if index < chunk_item_idx:
                chunk_idx = i
                index = index - chunk_item_idx
                break
            chunk_item_idx += chunk_used[i]

        if chunk_idx < 0:
            raise IndexError("list index out of range")
        if self.chunk_list[chunk_idx] is None:
            self._fetch_chunk_(chunk_idx)
        self.chunk_list[chunk_idx].insert(index, item)

        # Update meta data
        ray.get(self._meta.chunk_used.set_nocache.remote(chunk_used))

    def remove(self, object item):
        index = self.index(item)
        self.pop(index)

    def pop(self, int index=-1):
        cdef int chunk_idx = -1
        cdef list chunk_used = self._fetch_chunk_usage_and_length(index)
        cdef int chunk_last_used = ray.get(self._meta.last_used_chunk.get_nocache.remote())
        cdef int chunk_item_idx = self.length
        cdef object found = None
        cdef int item_idx = 0

        if index < 0:
            index = self.length + index

        # find target chunk list (from backward, assuming most pop happens at the end)
        assert chunk_last_used >= 0 and chunk_last_used < self.num_chunks,\
            f"chunk_last_used [{chunk_last_used}] is out of range"
        # TODO: make this search as a function
        for i in range(chunk_last_used, -1, -1):
            chunk_item_idx -= chunk_used[i]
            if index >= chunk_item_idx:
                chunk_idx = i   # found the chunk
                item_idx = index - chunk_item_idx # index within the chunk
                break
        if chunk_idx < 0:
            raise IndexError(f"list index out of range :: {index} / last_used_chunk={chunk_last_used} / chunk_used={chunk_used}")
        # Get the item
        if self.chunk_list[chunk_idx] is None:
            self._fetch_chunk_(chunk_idx)
        found = self.chunk_list[chunk_idx].pop(item_idx)
        # TODO: lazy resizing
        # Shift items after this chunk
        for i in range(chunk_idx+1, chunk_last_used+1):
            if self.chunk_list[i] is None:
                self._fetch_chunk_(i)
            assert len(self.chunk_list[i]) > 0,\
                f"Chunk {i} is empty, but in the middle (chunk_last_used={chunk_last_used})"
            self.chunk_list[i-1].append(self.chunk_list[i].pop(0))
        # Update the chunk_used for the last_used_chunk
        chunk_used[chunk_last_used] -= 1
        assert chunk_used[chunk_last_used] == len(self.chunk_list[chunk_last_used]),\
            f"chunk_used[{chunk_last_used}] != the chunk length[{len(self.chunk_list[chunk_last_used])}]"
        ray.get(self._meta.chunk_used.set_nocache.remote(chunk_used))
        if chunk_used[chunk_last_used] == 0:
            ray.get(self._meta.last_used_chunk.set_nocache.remote(chunk_last_used-1))

        self.length -= 1
        return found

    def clear(self):
        # Flush any items in the cache
        self._ensure_chunks_()
        for idx, chunk in enumerate(self.chunk_list):
            # Clear the chunk and write back
            chunk.clear()
            # self._evict_chunk_(idx)   # Make it lazy eviction (at release time)

        # Reset the meta data
        self.length = 0
        ray.get(self._meta.last_used_chunk.set_nocache.remote(0))
        chunk_used = [0 for _ in range(self.num_chunks)]
        ray.get(self._meta.chunk_used.set_nocache.remote(chunk_used))

    def index(self, object item, int start=0, int end=-1):
        cdef int chunk_idx = ray.get(self._meta.last_used_chunk.get_nocache.remote())
        cdef list chunk_used = ray.get(self._meta.chunk_used.get_nocache.remote())
        cdef int item_idx = 0
        for i in range(start, chunk_idx+1):
            if self.chunk_list[i] is None:
                self._fetch_chunk_(i)
            if item in self.chunk_list[i]:
                return item_idx + self.chunk_list[i].index(item)
            item_idx += chunk_used[i]
            if end != -1 and item_idx >= end:
                break
        raise ValueError(f"{item} is not in list")

    def __contains__(self, object item):
        try:
            self.index(item)
            return True
        except ValueError:
            return False

    def __iter__(self):
        for i in range(self.__len__()):
            yield self[i]

    def __reduce__(self):
        return (self.rebuild, (self.chunk_ref_list, self.num_chunks, self._roy_meta_ref, self.length, self._lock, self.per_chunk_lock, self._meta))

    @staticmethod
    def rebuild(chunk_ref_list, num_chunks, meta_ref, length, lock, per_chunk_lock, meta):
        return RoyList(num_chunks, None, lock, per_chunk_lock, chunk_ref_list, meta_ref, length, meta)

    def __repr__(self):
        return f"RoyList({self.chunk_list})"
