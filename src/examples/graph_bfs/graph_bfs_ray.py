import ray
import ray.util.queue as queue
from graph_bfs_base import run_bfs

@ray.remote
class SharedState:
    def __init__(self):
        self.visited = set()
        self.queue = queue.Queue()

    def add_nodes_to_queue(self, node_ids):
        added_any = False
        for node_id in node_ids:
            if node_id not in self.visited:
                self.queue.put(node_id)
                added_any = True
        return added_any

    def get_next_node(self):
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None

    def mark_visited(self, node_id):
        self.visited.add(node_id)

    def is_visited(self, node_id):
        return node_id in self.visited

@ray.remote
class Worker:
    def __init__(self, shared_state, graph, target_value):
        self.shared_state = shared_state
        self.graph = graph
        self.target_value = target_value

    def search(self):
        while True:
            node_id = ray.get(self.shared_state.get_next_node.remote())
            if node_id is None:
                break

            if node_id == self.target_value:
                print(f"Found target node: {node_id}")
                return node_id

            self.shared_state.mark_visited.remote(node_id)
            neighbors = self.graph.nodes[node_id].neighbors
            # batched enqueuing to reduce network messages
            self.shared_state.add_nodes_to_queue.remote(neighbors)

def distributed_bfs(graph, start_node, target_value, num_workers=4):
    # Initialize the shared state actor
    shared_state = SharedState.remote()

    # Add the starting node to the queue
    ray.get(shared_state.add_nodes_to_queue.remote([start_node]))

    # Initialize worker actors
    workers = [Worker.remote(shared_state, graph, target_value) for _ in range(num_workers)]

    # Start the search
    results = ray.get([worker.search.remote() for worker in workers])

    # Check if target was found
    for result in results:
        if result is not None:
            print(f"Target node {result} found.")
            break

# Example usage
if __name__ == "__main__":
    ray.init()
    run_bfs(distributed_bfs)
    ray.shutdown()
    
