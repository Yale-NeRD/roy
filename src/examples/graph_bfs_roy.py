import ray
import sys
import os

# Add root directory to the sys path
current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(current_directory)
sys.path.append(parent_directory)
sys.path.append(parent_directory + '/cpproy')
sys.path.append(parent_directory + '/roytypes')

from roytypes import RoySet, RoyList, remote, remote_worker

import ray  # `pip install ray` for this example
from graph_bfs_base import run_bfs
from ray.util.queue import Queue

@remote
class SharedState:
    def __init__(self):
        self.visited = RoySet()
        self.queue = Queue()
        self.found = RoyList()

# See the similarity with the single-threaded program
@remote_worker
class Worker:
    def __init__(self, shared_state, graph):
        self.shared_state = shared_state    # just a reference, out of sync
        self.graph = graph                  # read only, utilizing Ray's method

    def get_next_node(self):
        with self.shared_state as shared_state:
            try:
                return shared_state.queue.get(timeout=0.1)
            except IndexError:
                return None
            except ray.util.queue.Empty:
                # no more nodes to process, exit
                return None

    def update_nodes(self, node_id):
        neighbors = self.graph.nodes[node_id].neighbors
        with self.shared_state as shared_state:
            shared_state.visited.add(node_id)
            for node_id in neighbors:
                if node_id not in shared_state.visited:
                    shared_state.queue.put(node_id)
            # Note) there is only one data transfer after the lock is released,
            #       unlike Ray who calls RPC multiple times

    def search(self, idx, target_value):
        # print(f"Worker {idx} | started - {str(ray.get_runtime_context().get_worker_id())}", flush=True)
        while True:
            node_id = self.get_next_node()
            if node_id is None:
                with self.shared_state as shared_state:
                    if True in shared_state.found:
                        # self.shared_state.roy_flush()
                        return None # target found by another worker
                # retry after sleep
                import time
                time.sleep(1)
                print(f"Worker {idx} | retry", flush=True)
                continue

            print(f"Worker {idx} | next node: {node_id}", flush=True)
            if node_id == target_value:
                with self.shared_state as shared_state:
                    shared_state.found.append(True)
                print(f"Found target node {idx}: {node_id}", flush=True)
                # self.shared_state.roy_flush()
                # print(f"Flushed {idx}", flush=True)
                return node_id

            self.update_nodes(node_id)

# Reuse Ray's scheduling runtime
def distributed_bfs(graph, start_node, target_value, num_workers=4):
    # Initialize the shared state actor
    shared_state_obj = SharedState()

    # Add the starting node to the queue
    with shared_state_obj as shared_state:
        shared_state.queue.put(start_node)

    # Initialize worker actors
    workers = [Worker.remote(shared_state_obj, graph) for _ in range(num_workers)]

    # Start the search
    results = ray.get([worker.search.remote(idx, target_value) for idx, worker in enumerate(workers)])

    # Check if target was found
    for result in results:
        if result is not None:
            print(f"Target node {result} found.")
            break

# Example usage
if __name__ == "__main__":
    try:
        ray.init(runtime_env={"py_modules": [parent_directory + "/roytypes"]})
        run_bfs(distributed_bfs)
    finally:
        ray.shutdown()

