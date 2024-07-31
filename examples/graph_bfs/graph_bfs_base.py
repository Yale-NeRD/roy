class Node:
    def __init__(self, node_id, neighbors=None):
        self.node_id = node_id
        self.neighbors = neighbors if neighbors else []

    def add_neighbor(self, neighbor_id):
        self.neighbors.append(neighbor_id)

class Graph:
    def __init__(self):
        self.nodes = {}

    def add_node(self, node_id):
        if node_id not in self.nodes:
            self.nodes[node_id] = Node(node_id)

    def add_edge(self, node_id1, node_id2):
        if node_id1 in self.nodes and node_id2 in self.nodes:
            self.nodes[node_id1].add_neighbor(node_id2)
            self.nodes[node_id2].add_neighbor(node_id1)
        else:
            raise ValueError(f"One or both nodes {node_id1}, {node_id2} not found in graph.")

def run_bfs(distributed_bfs: callable):
    g = Graph()
    g.add_node(1)
    g.add_node(2)
    g.add_node(3)
    g.add_node(4)
    g.add_edge(1, 2)
    g.add_edge(1, 3)
    g.add_edge(2, 4)
    g.add_edge(3, 4)

    distributed_bfs(g, start_node=1, target_value=4)