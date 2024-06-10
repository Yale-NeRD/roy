# = deprecated =

# import os, sys
# script_dir = os.path.dirname(__file__)
# parent_directory = os.path.dirname(script_dir)
# sys.path.append(parent_directory)
# sys.path.append(parent_directory + '/cythonroy')
# from roytypes import roylist

# num_nodes = int(1e7)
# original_list = [float(i) for i in range(num_nodes)]
# arr = roylist.ChunkedArray(original_list)
# builtin_arr = original_list
# repeat = 100000

# # Measure performance
# import time
# start = time.time()
# for idx in range(repeat):
#     result = arr[idx % num_nodes]
# end = time.time()
# print(f"Cython Result: {result}, Time taken: {(end - start) * 1e9 / repeat} ns")

# start = time.time()
# for idx in range(repeat):
#     result = builtin_arr[idx % num_nodes]
# end = time.time()
# print(f"Python Result: {result}, Time taken: {(end - start) * 1e9 / repeat} ns")

