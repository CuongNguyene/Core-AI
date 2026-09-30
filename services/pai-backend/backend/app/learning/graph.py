from collections import defaultdict, deque

from app.learning.schemas import PrerequisiteEdge, PrerequisiteNode


def validate_prerequisite_graph(
    nodes: list[PrerequisiteNode], edges: list[PrerequisiteEdge]
) -> None:
    node_ids = {node.id for node in nodes}
    if len(node_ids) != len(nodes):
        raise ValueError("duplicate prerequisite node")

    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree = {node_id: 0 for node_id in node_ids}
    for edge in edges:
        if edge.from_node_id not in node_ids or edge.to_node_id not in node_ids:
            raise ValueError("unknown prerequisite node")
        if edge.from_node_id == edge.to_node_id:
            raise ValueError("prerequisite self-edge")
        if edge.to_node_id in adjacency[edge.from_node_id]:
            raise ValueError("duplicate prerequisite edge")
        adjacency[edge.from_node_id].add(edge.to_node_id)
        indegree[edge.to_node_id] += 1

    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for child in adjacency[node_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(node_ids):
        raise ValueError("prerequisite graph contains cycle")
