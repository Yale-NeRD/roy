import ray
from roy_on_ray import RoySet, RoyList, remote
from graph_bfs_base import run_bfs
from ray.util.queue import Queue

@remote
class SharedState:
    def __init__(self):
        self.visited = RoySet()
        self.queued = RoySet()
        self.queue = Queue()
        self.found = RoyList()

# See the similarity with the single-threaded program
@ray.remote
class Worker:
    def __init__(self, shared_state, graph):
        self.shared_state = shared_state    # just a reference, out of sync
        self.graph = graph                  # read only, utilizing Ray's method

    def get_next_node(self):
        with self.shared_state as shared_state:
            try:
                node_id = shared_state.queue.get(timeout=0.1)
                shared_state.queued.remove(node_id)
                return node_id
            except IndexError:
                return None
            except ray.util.queue.Empty:
                # no more nodes to process, exit
                return None

    def update_nodes(self, idx, node_id):
        neighbors = self.graph.nodes[node_id].neighbors
        print(f"Worker {idx} | node_id: {node_id} | neighbors: {neighbors}", flush=True)
        with self.shared_state as shared_state:
            shared_state.visited.add(node_id)
            print(f"Worker {idx} | node_id: {node_id} | visited: {shared_state.visited}", flush=True)
            for neighbor_id in neighbors:
                if neighbor_id not in shared_state.visited and neighbor_id not in shared_state.queued:
                    shared_state.queue.put(neighbor_id)
                    shared_state.queued.add(neighbor_id)  # Add to the set when queued
                    print(f"Worker {idx} | neighbor_id: {neighbor_id} | added to queue", flush=True)
            # Note) there is only one data transfer after the lock is released,
            #       unlike Ray who calls RPC multiple times

    def search(self, idx, target_value):
        while True:
            node_id = self.get_next_node()
            if node_id is None:
                with self.shared_state as shared_state:
                    if True in shared_state.found:
                        # self.shared_state.roy_flush()
                        print(f"Worker {idx} | target found by another worker", flush=True)
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
                return node_id

            self.update_nodes(idx, node_id)

# Reuse Ray's scheduling runtime
def distributed_bfs(graph, start_node, target_value, num_workers=4):
    # Initialize the shared state actor
    shared_state_obj = SharedState()

    # Add the starting node to the queue
    with shared_state_obj as shared_state:
        shared_state.queue.put(start_node)
        shared_state.queued.add(start_node)

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
        ray.init()
        run_bfs(distributed_bfs)
    finally:
        ray.shutdown()
