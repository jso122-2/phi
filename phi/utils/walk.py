"""
Neighborhood Walk Ordering for Samba SSM
The SSM is order-sensitive, so how we sequence a node's neighbors matters.
Different strategies expose different inductive biases.
"""
import random
from typing import List, Tuple

import networkx as nx


def order_neighbors(
    G: nx.DiGraph,
    node_id: int,
    strategy: str = "recency",
    max_neighbors: int = 16,
) -> List[Tuple[int, int, float]]:
    """
    Return an ordered list of (neighbor_id, edge_type_id, weight) for node_id.

    Strategies:
        recency     — sort by node_id descending (proxy for creation recency
                      when node_id is assigned in order of discovery)
        similarity  — sort by edge weight descending (strongest first)
        degree      — sort by neighbor degree descending (hub-first traversal)
        random      — random shuffle (augmentation during training)
        bfs         — BFS-order from node outward (preserves graph structure)

    The ordering defines the SSM's "time axis" — the model learns dynamics
    along this trajectory through the neighborhood.
    """
    if node_id not in G:
        return []

    # collect all neighbors (both in and out for undirected-style aggregation)
    neighbors = []
    for nbr in G.successors(node_id):
        edge_data = G.edges[node_id, nbr]
        neighbors.append((nbr, edge_data.get("edge_type_id", 0), edge_data.get("weight", 1.0)))
    for nbr in G.predecessors(node_id):
        if nbr not in [n[0] for n in neighbors]:
            edge_data = G.edges[nbr, node_id]
            neighbors.append((nbr, edge_data.get("edge_type_id", 0), edge_data.get("weight", 1.0)))

    if not neighbors:
        return []

    if strategy == "recency":
        # higher node_id → more recently added → first in sequence
        neighbors.sort(key=lambda x: x[0], reverse=True)

    elif strategy == "similarity":
        # strongest edge first
        neighbors.sort(key=lambda x: x[2], reverse=True)

    elif strategy == "degree":
        # high-degree neighbors first (hubs anchor the SSM sequence)
        neighbors.sort(key=lambda x: G.degree(x[0]), reverse=True)

    elif strategy == "random":
        random.shuffle(neighbors)

    elif strategy == "bfs":
        # BFS from node_id, collect in traversal order
        visited = {node_id}
        queue = [n for n in G.successors(node_id)]
        ordered_ids = []
        while queue and len(ordered_ids) < max_neighbors:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                ordered_ids.append(curr)
                queue.extend(G.successors(curr))
        nbr_dict = {n[0]: n for n in neighbors}
        neighbors = [nbr_dict[i] for i in ordered_ids if i in nbr_dict]

    return neighbors[:max_neighbors]


def random_walk_sequence(
    G: nx.DiGraph,
    start_node: int,
    walk_length: int = 16,
    restart_prob: float = 0.15,
) -> List[int]:
    """
    Personalized random walk from start_node.
    Used for data augmentation — creates alternative orderings.
    restart_prob: probability of teleporting back to start (PageRank-style).
    """
    if start_node not in G or G.degree(start_node) == 0:
        return [start_node]

    walk = [start_node]
    current = start_node
    for _ in range(walk_length - 1):
        if random.random() < restart_prob:
            current = start_node
        else:
            successors = list(G.successors(current)) + list(G.predecessors(current))
            if not successors:
                current = start_node
            else:
                current = random.choice(successors)
        walk.append(current)
    return walk
