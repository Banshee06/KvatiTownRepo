"""
planning.py
===========
Loads your map.yaml, builds a directed graph, runs Dijkstra to find
the shortest path from start → goal, then hands out one turn action
per intersection stop-line event.

HOW TO CUSTOMISE
----------------
1. Edit config/map.yaml  → the graph is loaded automatically.
2. Edit TURN_MAP below   → fill in 'straight'/'left'/'right' for each
   (from_node, to_node) pair that involves an intersection decision.
   Curve nodes need no entry because the bot just follows the lane.
"""

import heapq
import os
import yaml
from typing import Dict, List, Optional, Tuple

# ------------------------------------------------

_CONFIG_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'config'
))
_MAP_FILE   = os.path.join(_CONFIG_DIR, 'project_map.yaml')

with open(_MAP_FILE) as _f:
    _map_data = yaml.safe_load(_f)

# Build adjacency list from edges section
# { node_id: [(neighbour_id, distance), ...] }
DUCKIETOWN_MAP: Dict[str, List[Tuple[str, float]]] = {}

for _node in _map_data.get('nodes', []):
    DUCKIETOWN_MAP[_node['id']] = []

for _edge in _map_data.get('edges', []):
    src  = _edge['from']
    dst  = _edge['to']
    dist = float(_edge['distance'])
    DUCKIETOWN_MAP.setdefault(src, []).append((dst, dist))

# Default start and goal from YAML (can be overridden at runtime)
DEFAULT_START = _map_data.get('default_start', None)
DEFAULT_GOAL  = _map_data.get('default_goal',  None)

print(f"[Planning] Map loaded: {len(DUCKIETOWN_MAP)} nodes, "
      f"{sum(len(v) for v in DUCKIETOWN_MAP.values())} directed edges")
print(f"[Planning] Default route: {DEFAULT_START} → {DEFAULT_GOAL}")

EDGE_HEADING: Dict[Tuple[str, str], str] = {
    ('n_0_0', 'n_1_0'): 'S',
    ('n_1_0', 'n_1_1'): 'E',
    ('n_1_1', 'n_4_1'): 'S',
    ('n_0_0', 'n_0_3'): 'E',
    ('n_0_3', 'n_0_6'): 'E',
    ('n_0_6', 'n_4_6'): 'S',
    ('n_4_6', 'n_8_6'): 'S',
    ('n_8_6', 'n_8_4'): 'W',
    ('n_8_4', 'n_4_4'): 'N',
    ('n_4_4', 'n_4_1'): 'W',
    ('n_4_4', 'n_4_6'): 'E',
    ('n_4_4', 'n_2_4'): 'N',
    ('n_2_4', 'n_2_3'): 'W',
    ('n_2_3', 'n_0_3'): 'N',
}

_TURN_TABLE = {
    ('N', 'N'): 'straight',
    ('N', 'E'): 'right',
    ('N', 'W'): 'left',
    ('S', 'S'): 'straight',
    ('S', 'W'): 'right',
    ('S', 'E'): 'left',
    ('E', 'E'): 'straight',
    ('E', 'S'): 'right',
    ('E', 'N'): 'left',
    ('W', 'W'): 'straight',
    ('W', 'N'): 'right',
    ('W', 'S'): 'left',
}

def compute_turn(prev: str, current: str, next_node: str) -> str:
    approach = EDGE_HEADING.get((prev, current))
    exit_dir  = EDGE_HEADING.get((current, next_node))
    if not approach or not exit_dir:
        print(f"[Navigator] WARNING: no heading for ({prev}→{current}→{next_node}), defaulting to straight")
        return 'straight'
    return _TURN_TABLE.get((approach, exit_dir), 'straight')


# DIJKSTRA
# ---------------------------------------------------------------------------

def dijkstra(
    graph: Dict[str, List[Tuple[str, float]]],
    start: str,
    goal:  str,
) -> Optional[List[str]]:
    """
    Standard min-heap Dijkstra on a weighted directed graph.
    Returns the cheapest node path [start, ..., goal], or None.
    """
    heap    = [(0.0, start, [start])]
    visited: Dict[str, float] = {}

    while heap:
        cost, node, path = heapq.heappop(heap)

        if node in visited:
            continue
        visited[node] = cost

        if node == goal:
            return path

        for neighbour, edge_cost in graph.get(node, []):
            if neighbour not in visited:
                heapq.heappush(heap, (cost + edge_cost, neighbour, path + [neighbour]))

    return None


# ---------------------------------------------------------------------------
# PATH → ACTION SEQUENCE
# ---------------------------------------------------------------------------

def _node_type(node_id: str) -> str:
    """Look up the tile type of a node from the loaded YAML."""
    for n in _map_data.get('nodes', []):
        if n['id'] == node_id:
            return n.get('type', 'unknown')
    return 'unknown'


def convert_path_to_actions(path: List[str]) -> List[str]:
    if len(path) < 2:
        return ['GOAL']
    actions: List[str] = []
    for i in range(1, len(path)):
        prev      = path[i - 1]
        current   = path[i]
        next_node = path[i + 1] if i + 1 < len(path) else None
        ntype     = _node_type(current)

        if i == len(path) - 1:
            actions.append('GOAL')
        elif ntype in ('cross3', 'cross4'):
            # WAS: TURN_MAP.get((prev, current), 'straight')
            # NOW: geometry-based, needs the next node too
            actions.append(compute_turn(prev, current, next_node))
        else:
            actions.append('follow')
    return actions

# NAVIGATOR CLASS — used by NavigationController


class Navigator:
    """
    Simple interface the FSM calls.

    nav = Navigator()                         # uses YAML defaults
    nav = Navigator(start='n_8_6', goal='n_2_3')

    At each intersection stop-line:
        action = nav.next_action()
        # returns 'straight' | 'left' | 'right' | 'follow' | 'GOAL'
    """

    def __init__(
        self,
        start: Optional[str] = None,
        goal:  Optional[str] = None,
    ):
        self.start = start or DEFAULT_START
        self.goal  = goal  or DEFAULT_GOAL

        if self.start is None or self.goal is None:
            raise ValueError(
                "No start/goal provided and map.yaml has no default_start/default_goal."
            )

        self.path = dijkstra(DUCKIETOWN_MAP, self.start, self.goal)

        if self.path is None:
            print(f"[Navigator] ⚠️  No path from {self.start!r} to {self.goal!r}!")
            self._actions: List[str] = []
        else:
            self._actions = convert_path_to_actions(self.path)
            total_dist = sum(
                e['distance']
                for e in _map_data.get('edges', [])
                if e['from'] in self.path and e['to'] in self.path
            )
            print(f"[Navigator] Route: {' → '.join(self.path)}")
            print(f"[Navigator] Actions: {self._actions}")

        self._index = 0

    # ------------------------------------------------------------------

    def has_route(self) -> bool:
        return self.path is not None and len(self._actions) > 0

    def is_complete(self) -> bool:
        return self._index >= len(self._actions)

    def peek_action(self) -> str:
        if self.is_complete():
            return 'GOAL'
        return self._actions[self._index]

    def next_action(self) -> str:
        """
        Consume and return the next action.
        Call this once per intersection stop-line event.
        """
        if self.is_complete():
            return 'GOAL'
        action = self._actions[self._index]
        self._index += 1
        remaining = len(self._actions) - self._index
        print(f"[Navigator] Action: {action!r}  ({remaining} remaining)")
        return action

    def progress(self) -> str:
        n    = len(self._actions)
        done = min(self._index, n)
        node = self.path[min(done, len(self.path) - 1)] if self.path else '?'
        return f"{node} → {self.goal}  step {done}/{n}  next={self.peek_action()!r}"