import ray
import sys
import os

# Add root directory to the sys path
current_directory = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(current_directory)
sys.path.append(parent_directory)

import pyroy.roy as roy
import ray  # `pip install ray` for this example
from graph_bfs_base import run_bfs

@roy.remote
class SharedState:
    def __init__(self):
        self.visited = set()
        self.queue = list()

# See the similarity with the single-threaded program
@ray.remote
class Worker:
    def __init__(self, shared_state_handle, graph, target_value):
        roy.connect()
        self.shared_state = roy.get_remote(shared_state_handle)    # just a reference, out of sync
        self.graph = graph                  # read only, utilizing Ray's method
        self.target_value = target_value

    def get_next_node(self):
        with self.shared_state as shared_state:
            try:
                return shared_state.queue.pop(0)
            except IndexError:
                return None

    def update_nodes(self, node_id):
        neighbors = self.graph.nodes[node_id].neighbors
        with self.shared_state as shared_state:
            shared_state.visited.add(node_id)
            for node_id in neighbors:
                if node_id not in shared_state.visited:
                    shared_state.queue.append(node_id)
            # Note) there is only one data transfer after the lock is released,
            #       unlike Ray who calls RPC multiple times

    def search(self):
        while True:
            node_id = self.get_next_node()
            if node_id is None:
                break

            if node_id == self.target_value:
                print(f"Found target node: {node_id}")
                return node_id

            self.update_nodes(node_id)

# Reuse Ray's scheduling runtime
def distributed_bfs(graph, start_node, target_value, num_workers=4):
    # Initialize the shared state actor
    shared_state_obj = SharedState()

    # Add the starting node to the queue
    with shared_state_obj as shared_state:
        shared_state.queue.append(start_node)

    # Initialize worker actors
    workers = [Worker.remote(shared_state_obj.roy_handle, graph, target_value) for _ in range(num_workers)]

    # Start the search
    results = ray.get([worker.search.remote() for worker in workers])

    # Check if target was found
    for result in results:
        if result is not None:
            print(f"Target node {result} found.")
            break

# Example usage
if __name__ == "__main__":
    try:
        # start server in a separate process
        server_proc = roy.initialize_test_env()

        # connect to the server for this process
        roy.connect()
        ray.init(runtime_env={"py_modules": [parent_directory + "/pyroy"]})
        run_bfs(distributed_bfs)
    finally:
        ray.shutdown()
        roy.clean_test_env(server_proc)
