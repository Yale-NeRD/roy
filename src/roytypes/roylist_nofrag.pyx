// import ray

// cdef class ChunkedArray:
//     cdef list values
//     cdef int len
    
//     def __init__(self, list values):
//         self.values = values
//         self.len = len(values)

//     def __getitem__(self, int idx):
//         return self.getitem(idx)

//     cpdef object getitem(self, int idx):
//         if idx >= self.len:
//             raise IndexError("Index out of range")
        
//         return self.values[idx]