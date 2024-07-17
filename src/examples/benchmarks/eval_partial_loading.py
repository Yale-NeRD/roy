import ray
import time
import pickle

import os, sys
# current_directory = os.path.dirname(os.path.abspath(__file__))
# parent_directory = os.path.dirname(current_directory)
script_dir = os.path.dirname(__file__)
parent_directory = os.path.dirname(script_dir)
sys.path.append(parent_directory)
sys.path.append(parent_directory + '/cpproy')
sys.path.append(parent_directory + '/roytypes')
import roy_shmem
# from cpproy import roylist
# from roytypes import RoySet
from roytypes import RoyList

num_nodes = int(1e6)
num_repeat = 3
num_workers = 4

@ray.remote
class Worker:
    def __init__(self):
        # print(parent_directory, flush=True)
        # print(os.environ.get('PYTHONPATH', ''), flush=True)
        pass

    def search(self, idx, node_ref, target_value, start_pos, range_pos, measure_threshold_ns=500):
        # from roytypes import roylist
        node_ref = node_ref[0]
        start_time = time.time()
        self.node_list = ray.get(node_ref)
        # if isinstance(self.node_list, Roylist):
            # C++ version
            # self.node_list = roylist.Roylist(self.node_list.chunk_ref_list, self.node_list.chunk_size, len(self.node_list))
            # Rust version
            # self.node_list = roy_shmem.Roylist(self.node_list.chunk_ref_list, self.node_list.chunk_size, len(self.node_list))
            # self.node_list = roy_shmem.Roylist(self.node_list.chunk_ref_list, self.node_list.chunk_size, len(self.node_list), idx)  # with prefetching
            # Cython
            # self.node_list = cythonroy.roylist.Roylist(self.node_list.chunk_ref_list, self.node_list.chunk_size, len(self.node_list))
        end_time = time.time()
        print(f"Time remote loading: {end_time - start_time} sec", flush=True)

        total_time = 0
        count = 0

        if isinstance(self.node_list, RoyList):
            self.node_list.__lock__()
        # print(f"Start searching {idx}", flush=True)
        for i in range(start_pos, start_pos + range_pos):
            start_time = time.perf_counter_ns()
            node_id = self.node_list[i]
            end_time = time.perf_counter_ns()
            time_per_access = end_time - start_time
            if time_per_access <= measure_threshold_ns:
                total_time += time_per_access
                count += 1

            if node_id == target_value:
                # print(f"Found target node: {node_id}", flush=True)
                break
        # print(f"End searching {idx} :: {isinstance(self.node_list, roylist.Roylist)}", flush=True)
        if isinstance(self.node_list, RoyList):
            self.node_list.__unlock__()

        # if isinstance(self.node_list, roy_shmem.Roylist):
        #     print(f"Access latency in rust: {self.node_list.get_access_latency()}", flush=True)

        average_time = total_time / count if count > 0 else 0
        return average_time

def list_search_partial(node_list, target_value, num_workers=num_workers):
    # Initialize the shared state actor
    # node_list_ref = ray.put(node_list)
    start_time = time.time()
    node_per_worker = len(node_list) // num_workers
    node_list_ref = [ray.put(node_list[i * node_per_worker:(i + 1) * node_per_worker]) for i in range(0, num_workers)]
    end_time = time.time()
    print(f"Time loading: {end_time - start_time} sec", flush=True)

    # Initialize worker actors
    workers = [Worker.remote() for idx in range(num_workers)]

    # Start the search
    worker_futures = []
    start_time = time.time()
    for idx, worker in enumerate(workers):
        # worker_futures.append(worker.search.remote(target_value, idx * len(node_list) // len(workers), len(node_list) // len(workers)))
        worker_futures.append(worker.search.remote(idx, [node_list_ref[idx]], target_value, 0, len(node_list) // len(workers)))
    results = [result for result in ray.get(worker_futures) if result is not None]
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} sec", flush=True)
    print(f"Avg time: {sum(results) / len(results)} ns", flush=True)
    return (end_time - start_time) * 1e6    # in microseconds
    # return sum(results) / len(results)

def list_search(node_list, target_value, num_workers=num_workers):
    start_time = time.time()
    # Initialize the shared state actor
    node_list_ref = ray.put(node_list)
    end_time = time.time()
    print(f"Time loading: {end_time - start_time} sec", flush=True)

    # Initialize worker actors
    workers = [Worker.remote() for _ in range(num_workers)]

    # Start the search
    worker_futures = []
    start_time = time.time()
    for idx, worker in enumerate(workers):
        worker_futures.append(worker.search.remote(idx, [node_list_ref], target_value, idx * len(node_list) // len(workers), len(node_list) // len(workers)))
    results = [result for result in ray.get(worker_futures) if result is not None]
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} sec", flush=True)
    print(f"Avg time: {sum(results) / len(results)} ns", flush=True)
    return (end_time - start_time) * 1e6    # in microseconds
    # return sum(results) / len(results)

def create_roy_list(value, chunk_size):
    # chunk_ref_list = []
    # chunk_size = int(chunk_size)
    # for i in range(0, len(value), chunk_size):
    #     chunk = value[i:i + chunk_size]
    #     chunk_ref_list.append(ray.put(chunk))
    # return RoyList(chunk_ref_list, chunk_size, len(value))
    return RoyList(value, chunk_size)

def list_search_roy(node_list, target_value, num_workers=num_workers):
    start_time = time.time()
    # Initialize the shared state actor
    roy_list = create_roy_list(node_list, len(node_list) // num_workers)
    node_list_ref = ray.put(roy_list)
    end_time = time.time()
    print(f"Time loading: {end_time - start_time} sec", flush=True)

    # Initialize worker actors
    workers = [Worker.remote() for _ in range(num_workers)]

    # Start the search
    worker_futures = []
    start_time = time.time()
    for idx, worker in enumerate(workers):
        worker_futures.append(worker.search.remote(idx, [node_list_ref], target_value, idx * len(node_list) // len(workers), len(node_list) // len(workers)))
    results = [result for result in ray.get(worker_futures) if result is not None]
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} sec", flush=True)
    print(f"Avg time: {sum(results) / len(results)} ns", flush=True)
    return (end_time - start_time) * 1e6    # in microseconds
    # return sum(results) / len(results)

# Example usage
if __name__ == "__main__":
    ray.init(runtime_env={"py_modules": [parent_directory + "/cpproy", parent_directory + "/roytypes"]})
    node_list = ["12345678901234567890123456789012345678901234567890123456789012341234567890123456789012345678901234567890123456789012345678901234" for i in range(num_nodes)]
    # node_list = [float(i) for i in range(num_nodes)]
    list_search_time_partial = ([list_search_partial(node_list, num_nodes // 2) for _ in range(num_repeat)])
    list_search_time = ([list_search(node_list, num_nodes // 2) for _ in range(num_repeat)])
    list_search_time_roy = ([list_search_roy(node_list, num_nodes // 2) for _ in range(num_repeat)])
    ray.shutdown()
    print(f"Average time:")
    print(f"partitioned [{sum(list_search_time_partial) / len(list_search_time_partial):.3f}] us")
    print(f"non-part-ed [{sum(list_search_time) / len(list_search_time):.3f}] us")
    print(f"on-demand [{sum(list_search_time_roy) / len(list_search_time_roy):.3f}] us")

'''
= example output =

For 100,000,000 nodes::
Average time:
partitioned [1211324.771] us
non-part-ed [2092497.905] us
on-demand [1617722.909] us

# cpp
Average time:
partitioned [1416816.314] us
non-part-ed [2736505.349] us
on-demand [2344455.004] us

# rust 4 workers
partitioned [1397961.696] us
non-part-ed [2701779.127] us
on-demand [1770343.701] us

# cython for 64-byte string
partitioned [1988321.622] us
non-part-ed [3257741.372] us
on-demand [1984654.665] us
'''