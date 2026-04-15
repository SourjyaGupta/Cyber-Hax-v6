from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import random
import string
import time

NODE_COUNT = 16
EXTRA_EDGES = 8
MINE_RATIO = 0.08
LOCK_RATIO = 0.12
MAP_W = 780
MAP_H = 720
TRAP_LIMIT = 3
DECOY_LIMIT = 3
STUN_TIME = 6.0
AI_MOVE_COOLDOWN = (1.25, 2.2)
MAX_HUMANS = 2
DEFAULT_AI_COUNT = 0
PASSWORD_LENGTH = 3
SWEEP_LIMIT = 2
PATCH_KIT_LIMIT = 2
SHIELD_DURATION = 12.0

BOOKLET_TEXT = [
    "help - list commands",
    "mission - summarize your current objective and best next step",
    "status - your node, distance to server, and active effects",
    "inventory - show passwords and utility counts",
    "scan - reveal neighbors of your current node",
    "sweep - reveal nodes within two hops",
    "hint - suggest the strongest route toward the server",
    "probe <id> - inspect a visible node for threats and opportunities",
    "move <id> - move to an adjacent node if it is unlocked",
    "path <id> - shortest path length from your current node",
    "reveal - temporarily reveal opponents and their nearby nodes",
    "collect - collect an access key from the current node",
    "recon <id> - view a scrambled hint for a locked node password",
    "unlock <id> <password|auto> - unlock a locked node",
    "trap - place a stun trap on your current node",
    "decoy - deploy a fake node connected to your current node",
    "stabilize - clear stun and activate a short shield",
    "log - view the most recent public events",
    "rematch - vote for another round after a finished match",
    "restart - restart the room and reset the room score",
    "quit - exit the client",
]


@dataclass
class Node:
    id: int
    pos: Tuple[int, int]
    neighbors: Set[int] = field(default_factory=set)
    locked: bool = False
    lock_pw: Optional[str] = None
    mine: bool = False
    decoy: bool = False
    server: bool = False
    collect_pw: Optional[str] = None
    collect_target: Optional[int] = None


@dataclass
class Player:
    name: str
    is_human: bool
    current: int
    discovered: Set[int] = field(default_factory=set)
    stunned_until: float = 0.0
    traps_left: int = TRAP_LIMIT
    decoys_left: int = DECOY_LIMIT
    alive: bool = True
    collected_pwds: Dict[int, str] = field(default_factory=dict)
    reveal_uses: int = 0
    reveal_nodes: Set[int] = field(default_factory=set)
    reveal_until: float = 0.0
    next_action_at: float = 0.0
    sweeps_left: int = SWEEP_LIMIT
    patch_kits: int = PATCH_KIT_LIMIT
    shield_until: float = 0.0


@dataclass
class GameState:
    nodes: Dict[int, Node]
    edges: Set[Tuple[int, int]]
    server_id: int
    players: List[Player]
    global_unlocks: Set[int] = field(default_factory=set)
    traps: Dict[int, int] = field(default_factory=dict)
    winner: Optional[str] = None
    log: List[str] = field(default_factory=list)
    available_human_starts: List[int] = field(default_factory=list)


def _rand_pos_in_map() -> Tuple[int, int]:
    margin = 40
    return (
        random.randint(margin, MAP_W - margin),
        random.randint(margin, MAP_H - margin),
    )


def _initial_discovery(nodes: Dict[int, Node], start: int, depth: int = 1) -> Set[int]:
    return {
        node_id
        for node_id, distance in bfs_distances(nodes, start).items()
        if distance <= depth
    }


def generate_graph(
    node_count: int = NODE_COUNT,
    extra_edges: int = EXTRA_EDGES,
    mine_ratio: float = MINE_RATIO,
    lock_ratio: float = LOCK_RATIO,
) -> Dict[int, Node]:
    nodes = {i: Node(i, _rand_pos_in_map()) for i in range(node_count)}
    remaining = list(nodes.keys())
    random.shuffle(remaining)
    connected = {remaining.pop()}
    edges = set()

    while remaining:
        a = random.choice(list(connected))
        b = remaining.pop()
        nodes[a].neighbors.add(b)
        nodes[b].neighbors.add(a)
        edges.add(tuple(sorted((a, b))))
        connected.add(b)

    node_ids = list(nodes.keys())
    attempts = 0
    target_edge_count = node_count - 1 + extra_edges
    while len(edges) < target_edge_count and attempts < node_count * 10:
        a, b = random.sample(node_ids, 2)
        edge = tuple(sorted((a, b)))
        if edge not in edges:
            nodes[a].neighbors.add(b)
            nodes[b].neighbors.add(a)
            edges.add(edge)
        attempts += 1

    specials = list(nodes.keys())
    random.shuffle(specials)

    lock_count = int(node_count * lock_ratio)
    mine_count = int(node_count * mine_ratio)
    locked_nodes = specials[:lock_count]
    for node_id in locked_nodes:
        password = "".join(random.choice(string.ascii_lowercase) for _ in range(PASSWORD_LENGTH))
        nodes[node_id].locked = True
        nodes[node_id].lock_pw = password

    mine_targets = [node_id for node_id in specials[lock_count:] if not nodes[node_id].locked]
    for node_id in mine_targets[:mine_count]:
        nodes[node_id].mine = True

    collectable_targets = [node_id for node_id in nodes if not nodes[node_id].locked and not nodes[node_id].mine]
    random.shuffle(collectable_targets)
    for locked_node_id, cache_node_id in zip(locked_nodes, collectable_targets):
        nodes[cache_node_id].collect_pw = nodes[locked_node_id].lock_pw
        nodes[cache_node_id].collect_target = locked_node_id

    return nodes


def bfs_distances(nodes: Dict[int, Node], start: int, pass_locked: bool = True) -> Dict[int, int]:
    from collections import deque

    distances = {start: 0}
    queue = deque([start])
    while queue:
        node_id = queue.popleft()
        for neighbor_id in nodes[node_id].neighbors:
            if neighbor_id in distances:
                continue
            if not pass_locked and nodes[neighbor_id].locked:
                continue
            distances[neighbor_id] = distances[node_id] + 1
            queue.append(neighbor_id)
    return distances


def choose_server_and_starts(nodes: Dict[int, Node], num_players: int) -> Tuple[int, List[int]]:
    candidates = random.sample(list(nodes.keys()), k=min(6, len(nodes)))
    best_server = None
    best_span = -1
    for candidate in candidates:
        distances = bfs_distances(nodes, candidate)
        span = max(distances.values())
        if span > best_span:
            best_span = span
            best_server = candidate

    server_id = best_server if best_server is not None else random.choice(list(nodes.keys()))
    nodes[server_id].server = True
    nodes[server_id].locked = False
    nodes[server_id].lock_pw = None

    distances_from_server = bfs_distances(nodes, server_id)
    by_distance: Dict[int, List[int]] = {}
    for node_id, distance in distances_from_server.items():
        by_distance.setdefault(distance, []).append(node_id)

    start_nodes: List[int] = []
    for distance in sorted(by_distance.keys(), reverse=True):
        pool = [node_id for node_id in by_distance[distance] if node_id != server_id]
        random.shuffle(pool)
        while pool and len(start_nodes) < num_players:
            start_nodes.append(pool.pop())
        if len(start_nodes) == num_players:
            break

    if len(start_nodes) < num_players:
        leftovers = [node_id for node_id in nodes if node_id != server_id and node_id not in start_nodes]
        random.shuffle(leftovers)
        start_nodes.extend(leftovers[: num_players - len(start_nodes)])

    return server_id, start_nodes


def shortest_path_next_step(
    nodes: Dict[int, Node],
    start: int,
    goal: int,
    pass_locked: bool = True,
) -> Optional[int]:
    from collections import deque

    parent = {start: None}
    queue = deque([start])
    while queue:
        node_id = queue.popleft()
        if node_id == goal:
            break
        for neighbor_id in nodes[node_id].neighbors:
            if neighbor_id in parent:
                continue
            if not pass_locked and nodes[neighbor_id].locked:
                continue
            parent[neighbor_id] = node_id
            queue.append(neighbor_id)

    if goal not in parent:
        return None

    current = goal
    previous = parent[current]
    while previous is not None and previous != start:
        current = previous
        previous = parent[current]
    return current


def build_new_game(max_humans: int = MAX_HUMANS, num_ai: int = DEFAULT_AI_COUNT) -> GameState:
    nodes = generate_graph()
    total_slots = max(1, max_humans + num_ai)
    server_id, starts = choose_server_and_starts(nodes, total_slots)

    human_starts = starts[:max_humans]
    ai_starts = starts[max_humans : max_humans + num_ai]

    edges = set()
    for node in nodes.values():
        for neighbor_id in node.neighbors:
            edges.add(tuple(sorted((node.id, neighbor_id))))

    now = time.monotonic()
    players: List[Player] = []
    for index, start_node in enumerate(ai_starts):
        players.append(
            Player(
                name=f"AI-{index + 1}",
                is_human=False,
                current=start_node,
                discovered=_initial_discovery(nodes, start_node, depth=1),
                next_action_at=now + random.uniform(*AI_MOVE_COOLDOWN),
            )
        )

    return GameState(
        nodes=nodes,
        edges=edges,
        server_id=server_id,
        players=players,
        available_human_starts=human_starts,
    )


def normalize_player_name(player_name: str) -> str:
    clean = " ".join(player_name.strip().split())
    if not clean:
        clean = "Player"
    return clean[:24]


def get_player(gs: GameState, player_name: str) -> Optional[Player]:
    lookup = player_name.lower()
    for player in gs.players:
        if player.name.lower() == lookup:
            return player
    return None


def add_human_player(gs: GameState, player_name: str) -> Tuple[Player, bool]:
    clean_name = normalize_player_name(player_name)
    existing = get_player(gs, clean_name)
    if existing is not None:
        existing.is_human = True
        return existing, False

    if not gs.available_human_starts:
        raise ValueError("This session is full.")

    start_node = gs.available_human_starts.pop(0)
    player = Player(
        name=clean_name,
        is_human=True,
        current=start_node,
        discovered=_initial_discovery(gs.nodes, start_node, depth=1),
    )
    gs.players.append(player)
    return player, True


def update_temporary_effects(gs: GameState, now: float) -> bool:
    changed = False
    for player in gs.players:
        if player.reveal_nodes and now >= player.reveal_until:
            player.reveal_nodes.clear()
            player.reveal_until = 0.0
            changed = True
    return changed


def _write(output, text: str) -> None:
    output.write(text + "\n")


def _append_public_event(gs: GameState, message: str) -> None:
    gs.log.append(message)


def _active_visible_nodes(player: Player) -> Set[int]:
    return set(player.discovered) | set(player.reveal_nodes)


def _consume_shield(player: Player, now: float) -> bool:
    if now < player.shield_until:
        player.shield_until = 0.0
        return True
    return False


def _nearest_access_key(gs: GameState, player: Player) -> Optional[Tuple[int, int]]:
    visible = _active_visible_nodes(player)
    distances = bfs_distances(gs.nodes, player.current)
    candidates = []
    for node_id in visible:
        node = gs.nodes[node_id]
        if node.collect_pw and node.collect_target is not None:
            candidates.append((distances.get(node_id, 999), node_id, node.collect_target))
    if not candidates:
        return None
    _, node_id, target_id = min(candidates)
    return node_id, target_id


def cmd_help(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    _write(output, "Available commands:")
    for line in BOOKLET_TEXT:
        _write(output, f" - {line}")


def cmd_mission(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    distance_to_server = bfs_distances(gs.nodes, player.current).get(gs.server_id)
    _write(output, f"Primary objective: breach server node {gs.server_id}.")
    if distance_to_server is not None:
        _write(output, f"Current path distance: {distance_to_server} hop(s).")

    if gs.nodes[player.current].collect_pw and gs.nodes[player.current].collect_target is not None:
        _write(
            output,
            f"Current node contains an access key for node {gs.nodes[player.current].collect_target}. Use 'collect'.",
        )

    next_step = shortest_path_next_step(gs.nodes, player.current, gs.server_id, pass_locked=True)
    if next_step is not None and next_step != player.current:
        next_node = gs.nodes[next_step]
        if next_node.locked and next_step not in gs.global_unlocks:
            _write(output, f"Best route points through locked node {next_step}. Use 'recon {next_step}' or 'unlock {next_step} auto'.")
        else:
            _write(output, f"Recommended move: node {next_step}.")

    nearest_key = _nearest_access_key(gs, player)
    if nearest_key is not None:
        cache_node, target_node = nearest_key
        _write(output, f"Nearest visible access key: collect at node {cache_node} to unlock node {target_node}.")


def cmd_status(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    distances = bfs_distances(gs.nodes, player.current)
    distance_to_server = distances.get(gs.server_id, "?")
    effects = []
    if now < player.stunned_until:
        effects.append(f"STUNNED {player.stunned_until - now:.1f}s")
    if now < player.shield_until:
        effects.append(f"SHIELDED {player.shield_until - now:.1f}s")
    _write(
        output,
        f"At node {player.current}. Distance to server: {distance_to_server}. "
        + (f"Effects: {', '.join(effects)}." if effects else "No active effects."),
    )
    neighbors = ", ".join(str(node_id) for node_id in sorted(gs.nodes[player.current].neighbors))
    _write(output, f"Neighbors: {neighbors if neighbors else '(none)'}")
    _write(
        output,
        f"Utilities: traps {player.traps_left} | decoys {player.decoys_left} | sweeps {player.sweeps_left} | patch kits {player.patch_kits}",
    )


def cmd_inventory(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    passwords = ", ".join(
        f"{node_id}:{password}" for node_id, password in sorted(player.collected_pwds.items())
    )
    if not passwords:
        passwords = "none"
    _write(output, f"Access keys: {passwords}")
    _write(
        output,
        f"Utilities: sweeps {player.sweeps_left}, patch kits {player.patch_kits}, traps {player.traps_left}, decoys {player.decoys_left}, reveal charges {max(0, 3 - player.reveal_uses)}",
    )
    if now < player.shield_until:
        _write(output, f"Shield active for {player.shield_until - now:.1f}s.")


def cmd_scan(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    player.discovered.add(player.current)
    player.discovered.update(gs.nodes[player.current].neighbors)
    _write(output, "Scan complete. Nearby connections updated.")


def cmd_sweep(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    if player.sweeps_left <= 0:
        _write(output, "No sweep charges remaining.")
        return

    before = len(player.discovered)
    revealed = _initial_discovery(gs.nodes, player.current, depth=2)
    player.discovered.update(revealed)
    player.sweeps_left -= 1
    _write(output, f"Deep sweep complete. Revealed {len(player.discovered) - before} additional node(s).")
    _append_public_event(gs, f"{player.name} ran a network sweep.")


def cmd_hint(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    next_step = shortest_path_next_step(gs.nodes, player.current, gs.server_id, pass_locked=True)
    if next_step is None:
        _write(output, "No route suggestion available from your current position.")
        return

    if gs.nodes[player.current].collect_pw and gs.nodes[player.current].collect_target is not None:
        _write(
            output,
            f"Tip: collect the access key here first. It unlocks node {gs.nodes[player.current].collect_target}.",
        )

    next_node = gs.nodes[next_step]
    if next_node.locked and next_step not in gs.global_unlocks:
        _write(output, f"Suggested route: node {next_step}, but it is still locked.")
        if next_step in player.collected_pwds:
            _write(output, f"You already hold the key. Use 'unlock {next_step} auto'.")
        else:
            _write(output, f"Use 'probe {next_step}' or 'recon {next_step}' before pushing forward.")
    else:
        _write(output, f"Suggested next hop: move {next_step}.")


def cmd_probe(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    if not args:
        _write(output, "Usage: probe <node_id>")
        return

    try:
        node_id = int(args[0])
    except ValueError:
        _write(output, "Node id must be an integer.")
        return

    if node_id not in gs.nodes:
        _write(output, "No such node.")
        return

    visible = _active_visible_nodes(player) | set(gs.nodes[player.current].neighbors)
    if node_id not in visible and node_id != player.current:
        _write(output, "Node is outside your current sensor range.")
        return

    node = gs.nodes[node_id]
    tags = []
    if node.server:
        tags.append("server")
    if node.locked and node_id not in gs.global_unlocks:
        tags.append("locked")
    if node.mine:
        tags.append("mine risk")
    if node.decoy:
        tags.append("decoy")
    if node.collect_pw and node.collect_target is not None:
        tags.append(f"access key for node {node.collect_target}")
    if not tags:
        tags.append("stable")

    _write(output, f"Node {node_id} :: {', '.join(tags)}")
    _write(output, f"Connections: {', '.join(str(neighbor) for neighbor in sorted(node.neighbors))}")


def cmd_move(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    if now < player.stunned_until:
        _write(output, "You are stunned and cannot move.")
        return
    if not args:
        _write(output, "Usage: move <node_id>")
        return

    try:
        target = int(args[0])
    except ValueError:
        _write(output, "Node id must be an integer.")
        return

    if target not in gs.nodes[player.current].neighbors:
        _write(output, f"Node {target} is not adjacent to {player.current}.")
        return

    node = gs.nodes[target]
    if node.locked and target not in gs.global_unlocks:
        _write(output, f"Node {target} is locked. Unlock it first.")
        return

    player.current = target
    player.discovered.add(target)
    _write(output, f"Moved to node {target}.")

    if target == gs.server_id:
        gs.winner = player.name
        _append_public_event(gs, f"{player.name} hacked the server.")
        _write(output, ">> SERVER HACKED! You win. <<")
        return

    if target in gs.traps and gs.traps[target] > 0:
        gs.traps[target] -= 1
        if _consume_shield(player, now):
            _write(output, "Your shield absorbed a trap pulse.")
        else:
            player.stunned_until = now + STUN_TIME + 2
            _write(output, "You triggered a trap and were stunned.")

    if node.mine:
        node.mine = False
        if _consume_shield(player, now):
            _write(output, "Your shield absorbed a mine blast.")
        else:
            player.stunned_until = now + STUN_TIME
            _write(output, "You hit a mine and were stunned.")


def cmd_path(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    if not args:
        _write(output, "Usage: path <node_id>")
        return

    try:
        target = int(args[0])
    except ValueError:
        _write(output, "Node id must be an integer.")
        return

    if target not in gs.nodes:
        _write(output, "No such node.")
        return

    distance = bfs_distances(gs.nodes, player.current).get(target)
    if distance is None:
        _write(output, "Path unknown.")
    else:
        _write(output, f"Shortest path length: {distance} step(s).")


def cmd_reveal(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    if player.reveal_uses >= 3:
        _write(output, "Reveal has already been used 3 times.")
        return

    player.reveal_uses += 1
    revealed_nodes = set()
    for rival in gs.players:
        if rival.name == player.name or not rival.alive:
            continue
        revealed_nodes.add(rival.current)
        revealed_nodes.update(gs.nodes[rival.current].neighbors)

    player.reveal_nodes = revealed_nodes
    player.reveal_until = now + 5.0
    _write(output, f"Revealing opponents for 5 seconds. ({player.reveal_uses}/3)")


def cmd_collect(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    node = gs.nodes[player.current]
    if node.collect_pw and node.collect_target is not None:
        player.collected_pwds[node.collect_target] = node.collect_pw
        node.collect_pw = None
        _append_public_event(gs, f"{player.name} collected an access key at node {player.current}.")
        _write(output, f"Collected the access key for node {node.collect_target}.")
        node.collect_target = None
    else:
        _write(output, "No access key is stored at this node.")


def cmd_recon(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    if not args:
        _write(output, "Usage: recon <node_id>")
        return

    try:
        node_id = int(args[0])
    except ValueError:
        _write(output, "Node id must be an integer.")
        return

    node = gs.nodes.get(node_id)
    if node is None:
        _write(output, "No such node.")
        return
    if not node.locked or not node.lock_pw:
        _write(output, "That node is not locked.")
        return

    scrambled = "".join(random.sample(node.lock_pw, k=len(node.lock_pw)))
    _write(output, f"Recon: password letters are {scrambled} (scrambled).")


def cmd_unlock(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    if len(args) != 2:
        _write(output, "Usage: unlock <node_id> <password>")
        return

    try:
        node_id = int(args[0])
    except ValueError:
        _write(output, "Node id must be an integer.")
        return

    node = gs.nodes.get(node_id)
    if node is None:
        _write(output, "No such node.")
        return
    if not node.locked:
        _write(output, "Node is not locked.")
        return

    guess = args[1].strip().lower()
    if guess == "auto":
        guess = player.collected_pwds.get(node_id, "")
        if not guess:
            _write(output, "You do not have a collected key for that node yet.")
            return
    if node.lock_pw == guess:
        node.locked = False
        gs.global_unlocks.add(node_id)
        _append_public_event(gs, f"{player.name} unlocked node {node_id}.")
        _write(output, f"Node {node_id} unlocked successfully.")
    else:
        _write(output, "Incorrect password. Node remains locked.")


def cmd_trap(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    if player.traps_left <= 0:
        _write(output, "No traps remaining.")
        return

    gs.traps[player.current] = gs.traps.get(player.current, 0) + 1
    player.traps_left -= 1
    _write(output, f"Trap placed at node {player.current}.")


def cmd_decoy(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    if player.decoys_left <= 0:
        _write(output, "No decoys remaining.")
        return

    new_id = max(gs.nodes.keys()) + 1
    decoy = Node(id=new_id, pos=_rand_pos_in_map(), decoy=True)
    gs.nodes[new_id] = decoy
    gs.nodes[player.current].neighbors.add(new_id)
    decoy.neighbors.add(player.current)
    gs.edges.add(tuple(sorted((player.current, new_id))))
    player.decoys_left -= 1
    _write(output, "Decoy deployed.")


def cmd_stabilize(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    if player.patch_kits <= 0:
        _write(output, "No patch kits remaining.")
        return

    player.patch_kits -= 1
    had_stun = now < player.stunned_until
    player.stunned_until = now
    player.shield_until = max(player.shield_until, now + SHIELD_DURATION)
    if had_stun:
        _write(output, f"Patch kit deployed. Movement restored and shield active for {SHIELD_DURATION:.0f}s.")
    else:
        _write(output, f"Patch kit deployed. Shield active for {SHIELD_DURATION:.0f}s.")


def cmd_log(gs: GameState, player: Player, output, now: float, args: List[str]) -> None:
    _write(output, "Recent public events:")
    for line in gs.log[-10:]:
        _write(output, f" - {line}")


COMMANDS = {
    "help": cmd_help,
    "mission": cmd_mission,
    "status": cmd_status,
    "inventory": cmd_inventory,
    "scan": cmd_scan,
    "sweep": cmd_sweep,
    "hint": cmd_hint,
    "probe": cmd_probe,
    "move": cmd_move,
    "path": cmd_path,
    "reveal": cmd_reveal,
    "collect": cmd_collect,
    "recon": cmd_recon,
    "unlock": cmd_unlock,
    "trap": cmd_trap,
    "decoy": cmd_decoy,
    "stabilize": cmd_stabilize,
    "log": cmd_log,
}


def handle_command(
    line: str,
    gs: GameState,
    player_name: str,
    output,
    now: Optional[float] = None,
) -> None:
    if now is None:
        now = time.monotonic()

    update_temporary_effects(gs, now)
    player = get_player(gs, player_name)
    if player is None:
        _write(output, "Player not registered in this session.")
        return

    parts = line.split()
    if not parts:
        return

    command = parts[0].lower()
    args = parts[1:]

    if command == "quit":
        _write(output, "Closing local client.")
        return

    fn = COMMANDS.get(command)
    if fn is None:
        _write(output, "Unknown command. Type 'help'.")
        return

    fn(gs, player, output, now, args)


def advance_game(gs: GameState, now: Optional[float] = None) -> bool:
    if now is None:
        now = time.monotonic()

    changed = update_temporary_effects(gs, now)
    if gs.winner:
        return changed

    for player in gs.players:
        if player.is_human or not player.alive:
            continue
        if now < player.stunned_until or now < player.next_action_at:
            continue

        player.next_action_at = now + random.uniform(*AI_MOVE_COOLDOWN)

        next_step = shortest_path_next_step(gs.nodes, player.current, gs.server_id, pass_locked=True)
        if next_step is None:
            neighbors = list(gs.nodes[player.current].neighbors)
            if not neighbors:
                continue
            next_step = random.choice(neighbors)

        target_node = gs.nodes[next_step]
        if target_node.locked and next_step not in gs.global_unlocks:
            if random.random() < 0.18 and target_node.lock_pw:
                guess = "".join(random.choice(string.ascii_lowercase) for _ in range(PASSWORD_LENGTH))
                if guess == target_node.lock_pw:
                    target_node.locked = False
                    gs.global_unlocks.add(next_step)
                    _append_public_event(gs, f"{player.name} unlocked node {next_step}.")
                    changed = True
            continue

        player.current = next_step
        player.discovered.add(next_step)
        changed = True

        if next_step == gs.server_id:
            gs.winner = player.name
            _append_public_event(gs, f"{player.name} hacked the server.")
            return True

        if next_step in gs.traps and gs.traps[next_step] > 0:
            gs.traps[next_step] -= 1
            player.stunned_until = now + STUN_TIME

        if target_node.mine:
            target_node.mine = False
            player.stunned_until = now + STUN_TIME

    return changed


def serialize_state(gs: GameState) -> dict:
    return {
        "nodes": {
            str(node_id): {
                "id": node.id,
                "pos": [node.pos[0], node.pos[1]],
                "neighbors": sorted(node.neighbors),
                "locked": node.locked,
                "mine": node.mine,
                "decoy": node.decoy,
                "server": node.server,
                "collect_pw": None,
                "collect_target": None,
                "lock_pw": None,
            }
            for node_id, node in gs.nodes.items()
        },
        "edges": [list(edge) for edge in sorted(gs.edges)],
        "server_id": gs.server_id,
        "players": [
            {
                "name": player.name,
                "is_human": player.is_human,
                "current": player.current,
                "discovered": sorted(player.discovered),
                "stunned_until": player.stunned_until,
                "traps_left": player.traps_left,
                "decoys_left": player.decoys_left,
                "alive": player.alive,
                "collected_pwds": {str(node_id): password for node_id, password in player.collected_pwds.items()},
                "reveal_uses": player.reveal_uses,
                "reveal_nodes": sorted(player.reveal_nodes),
                "reveal_until": player.reveal_until,
                "next_action_at": player.next_action_at,
                "sweeps_left": player.sweeps_left,
                "patch_kits": player.patch_kits,
                "shield_until": player.shield_until,
            }
            for player in gs.players
        ],
        "global_unlocks": sorted(gs.global_unlocks),
        "traps": {str(node_id): count for node_id, count in gs.traps.items()},
        "winner": gs.winner,
        "log": list(gs.log),
        "available_human_starts": list(gs.available_human_starts),
    }


def deserialize_state(data: dict) -> GameState:
    nodes = {
        int(node_id): Node(
            id=int(node_data["id"]),
            pos=(int(node_data["pos"][0]), int(node_data["pos"][1])),
            neighbors={int(neighbor_id) for neighbor_id in node_data.get("neighbors", [])},
            locked=bool(node_data.get("locked", False)),
            lock_pw=node_data.get("lock_pw"),
            mine=bool(node_data.get("mine", False)),
            decoy=bool(node_data.get("decoy", False)),
            server=bool(node_data.get("server", False)),
            collect_pw=node_data.get("collect_pw"),
            collect_target=node_data.get("collect_target"),
        )
        for node_id, node_data in data.get("nodes", {}).items()
    }

    players = [
        Player(
            name=player_data["name"],
            is_human=bool(player_data.get("is_human", False)),
            current=int(player_data["current"]),
            discovered={int(node_id) for node_id in player_data.get("discovered", [])},
            stunned_until=float(player_data.get("stunned_until", 0.0)),
            traps_left=int(player_data.get("traps_left", TRAP_LIMIT)),
            decoys_left=int(player_data.get("decoys_left", DECOY_LIMIT)),
            alive=bool(player_data.get("alive", True)),
            collected_pwds={
                int(node_id): password for node_id, password in player_data.get("collected_pwds", {}).items()
            },
            reveal_uses=int(player_data.get("reveal_uses", 0)),
            reveal_nodes={int(node_id) for node_id in player_data.get("reveal_nodes", [])},
            reveal_until=float(player_data.get("reveal_until", 0.0)),
            next_action_at=float(player_data.get("next_action_at", 0.0)),
            sweeps_left=int(player_data.get("sweeps_left", SWEEP_LIMIT)),
            patch_kits=int(player_data.get("patch_kits", PATCH_KIT_LIMIT)),
            shield_until=float(player_data.get("shield_until", 0.0)),
        )
        for player_data in data.get("players", [])
    ]

    return GameState(
        nodes=nodes,
        edges={tuple(int(part) for part in edge) for edge in data.get("edges", [])},
        server_id=int(data["server_id"]),
        players=players,
        global_unlocks={int(node_id) for node_id in data.get("global_unlocks", [])},
        traps={int(node_id): int(count) for node_id, count in data.get("traps", {}).items()},
        winner=data.get("winner"),
        log=list(data.get("log", [])),
        available_human_starts=[int(node_id) for node_id in data.get("available_human_starts", [])],
    )


def visible_nodes_for_player(gs: GameState, player_name: str) -> Set[int]:
    player = get_player(gs, player_name)
    if player is None:
        return set()
    return _active_visible_nodes(player)
