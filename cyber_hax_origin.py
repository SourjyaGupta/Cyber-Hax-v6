# cyber_hax.py
# Cyber Hax – playable prototype with scrollable booklet & terminal + command history
# Compatible: Python 3.13, pygame 2.6.1

import random
import string
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import threading
import math
import pygame
import datetime
import os

import asyncio, websockets, threading, json

SERVER_URL = "ws://localhost:8000/ws/session1"

def start_network_listener(term):
    async def listener():
        async with websockets.connect(SERVER_URL) as ws:
            async for msg in ws:
                data = json.loads(msg)
                if data["type"] == "log":
                    for line in data["lines"]:
                        term.add(line)
    threading.Thread(target=lambda: asyncio.run(listener()), daemon=True).start()

async def send_command(line):
    async with websockets.connect(SERVER_URL) as ws:
        await ws.send(json.dumps({"type": "command", "command": line}))


print(os.getcwd())



class ChatMessage:
    def __init__(self, sender, text):
        self.sender = sender
        self.text = text
        self.time = datetime.datetime.now().strftime("%H:%M")

class ChatSystem:
    def __init__(self, x, y, width, height, font):
        self.rect = pygame.Rect(x, y, width, height)
        self.font = font
        self.input_text = ""
        self.messages = []
        self.active = True           # typing focus
        self.visible = True         # collapsed by default
        self.awaiting_reply = False
        self.reply_delay = 0
        self.bot_replies = {
            "hello": "Hello, user.",
            "who are you": "System online. Monitoring your activity.",
            "status": "All systems running at 98% efficiency.",
            "bye": "System shutting down connection..."
        }

        # toggle button rectangle
        self.toggle_rect = pygame.Rect(10, self.rect.bottom - 45, 36, 36)

    def handle_event(self, event):
        if not self.visible:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                text = self.input_text.strip()
                if text:
                    self.add_message("You", text)
                    self.pending_message = text
                    self.input_text = ""
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.toggle()
            else:
                if len(event.unicode) == 1:
                    self.input_text += event.unicode


    def update(self):
        # trigger system reply after delay
        if self.awaiting_reply and pygame.time.get_ticks() > self.reply_delay:
            last = self.messages[-1].text.lower()
            reply = "..."
            for k, v in self.bot_replies.items():
                if k in last:
                    reply = v
                    break
            if reply == "...":
                reply = "System cannot parse input."
            self.add_message("System", reply)
            self.awaiting_reply = False

    def add_message(self, sender, text):
        self.messages.append(ChatMessage(sender, text))
        if len(self.messages) > 25:
            self.messages.pop(0)

    def draw(self, surf):
        if not self.visible:
            return

        x, y = 20, H - self.height - 20
        rect = pygame.Rect(x, y, self.width, self.height)

        pygame.draw.rect(surf, (220, 220, 255), rect)  # Background
        pygame.draw.rect(surf, (100, 100, 200), rect, 2)  # Border

        offset_y = y + 10
        for msg in self.messages:
            sender = msg.sender
            text = msg.text
            color = (30, 30, 130) if sender == "You" else (0, 180, 130)
            bubble_text = f"{sender}: {text}"
            wrapped_lines = self.wraplines(bubble_text, self.font, self.width - 30)
            for line in wrapped_lines:
                surf.blit(self.font.render(line, True, color), (x + 10, offset_y))
                offset_y += 22

        input_rect = pygame.Rect(x + 10, rect.bottom - 28, rect.w - 20, 20)
        pygame.draw.rect(surf, (255, 255, 255), input_rect)
        text_surface = self.font.render(self.input_text, True, (30, 30, 130))
        surf.blit(text_surface, (input_rect.x + 5, input_rect.y + 2))


        # Input line box and text
        input_rect = pygame.Rect(x + 10, rect.bottom - 28, rect.w - 20, 20)
        pygame.draw.rect(surf, (255, 255, 255), input_rect)  # Input box background color
        text_surface = self.font.render(self.input_text, True, (30, 30, 130))  # Input text color
        surf.blit(text_surface, (input_rect.x + 5, input_rect.y + 2))

class Particle:
    def __init__(self, x, y):
        self.x = x + random.randint(-20, 20)
        self.y = y
        self.radius = random.randint(2, 5)
        self.alpha = 120
        self.speed_y = random.uniform(-0.2, -0.5)
    
    def update(self):
        self.y += self.speed_y
        self.alpha -= 0.3
    
    def draw(self, surface):
        if self.alpha > 0:
            s = pygame.Surface((self.radius*2, self.radius*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (200,200,255,int(self.alpha)), (self.radius,self.radius), self.radius)
            surface.blit(s, (self.x - self.radius, self.y - self.radius))

    def draw_edge(screen, n1, n2, color):
        pygame.draw.line(screen, color, (n1.x, n1.y), (n2.x, n2.y), 2)


def draw_node(screen, x, y, color, pulse):
    glow = int((math.sin(pulse) + 1) * 50)  # soft oscillation
    final_color = (min(color[0]+glow,255), min(color[1]+glow,255), min(color[2]+glow,255))
    pygame.draw.circle(screen, final_color, (x, y), 10 + int(glow/20))

# ----------------------------- Config ---------------------------------
INTRO_LINES = [
    "Welcome Aboard the <<RMS Lateron>>",
    "",
    "Deep within the ship's metal shell,",
    "A single <<server>> runs everything from an isolated cabin.",
    "",
    "Your objective is simple: <<Shut down the Lateron server>>",
    "",
    "But you are not alone.",
    "Multiple factions are moving through the other cabins,",
    "All racing to strike the final blow.",
    "",
    "You must succeed <<before they do>>.",
    "The first one to complete the shutdown earns the time needed to <<escape>>",
]

W, H = 1200, 720  # Default/fallback values
SIDEBAR_W = 420
MAP_W = W - SIDEBAR_W

FPS = 60

NODE_COUNT = random.randint(25, 35)
EXTRA_EDGES = 18
MINE_RATIO = 0.12
LOCK_RATIO = 0.18

NUM_AI = 2
STUN_TIME = 10
AI_MOVE_COOLDOWN = (0.9, 1.6)   # default AI speed (adjust as you like)
HUMAN_SCAN_REVEAL_NEIGHBORS = True
TRAP_LIMIT = 3
DECOY_LIMIT = 3
FONT_SIZE = 18
TITLE_FONT_SIZE = 30

NODE_RADIUS = 12
SERVER_RADIUS = 14
CURRENT_HALO = 22
EDGE_THICKNESS = 5

BG = (8, 10, 18)
MAP_BG = (14, 16, 22)
FG = (220, 220, 220)
MUTED = (120, 130, 150)
ACCENT = (255, 80, 120)
DANGER = (255, 95, 95)
LOCKED_COL = (255, 190, 100)
MINE_COL = (255, 140, 140)
SERVER_COL = (140, 255, 180)


# ------------------------- Data structures ----------------------------

@dataclass
class Node:
    id: int
    pos: Tuple[int, int]
    neighbors: Set[int] = field(default_factory=set)
    locked: bool = False
    lock_pw: Optional[str] = None
    stored_pw: Optional[str] = None  # Password given at another node (Node A
    mine: bool = False
    decoy: bool = False
    server: bool = False
    collect_pw: Optional[str] = None  # NEW: password you can collect

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
    collected_pwds: Dict[int, str] = field(default_factory=dict)  # NEW

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

# ------------------------- Utility ------------------------------------

def _rand_pos_in_map() -> Tuple[int, int]:
    margin = 40
    return (random.randint(margin, MAP_W - margin),
            random.randint(margin, H - margin))

def generate_graph() -> Dict[int, Node]:
    nodes = {i: Node(i, _rand_pos_in_map()) for i in range(NODE_COUNT)}
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
    
    # Add extra edges
    node_ids = list(nodes.keys())
    attempts = 0
    while len(edges) < NODE_COUNT - 1 + EXTRA_EDGES and attempts < NODE_COUNT * 10:
        a, b = random.sample(node_ids, 2)
        e = tuple(sorted((a, b)))
        if e not in edges:
            nodes[a].neighbors.add(b)
            nodes[b].neighbors.add(a)
            edges.add(e)
        attempts += 1

    # Locked nodes
    specials = list(nodes.keys())
    random.shuffle(specials)
    lock_count = int(NODE_COUNT * LOCK_RATIO)
    mine_count = int(NODE_COUNT * MINE_RATIO)
    for nid in specials[:lock_count]:
        pw = ''.join(random.choice(string.ascii_lowercase) for _ in range(4))  # 4-letter password
        nodes[nid].locked = True
        nodes[nid].lock_pw = pw

    # Mines
    mine_targets = [n for n in specials[lock_count:] if not nodes[n].locked]
    for nid in mine_targets[:mine_count]:
        nodes[nid].mine = True

    # Collectible passwords
    collect_nodes = random.sample([n for n in nodes if not nodes[n].locked], k=max(3, NODE_COUNT//6))
    for nid in collect_nodes:
        nodes[nid].collect_pw = ''.join(random.choice(string.ascii_lowercase) for _ in range(4))  # 4-letter collectible

    return nodes

def bfs_distances(nodes: Dict[int, Node], start: int, pass_locked=True) -> Dict[int, int]:
    from collections import deque
    dist = {start: 0}
    dq = deque([start])
    while dq:
        u = dq.popleft()
        for v in nodes[u].neighbors:
            if v in dist:
                continue
            if not pass_locked and nodes[v].locked:
                continue
            dist[v] = dist[u] + 1
            dq.append(v)
    return dist

def choose_server_and_starts(nodes: Dict[int, Node], num_players: int) -> Tuple[int, List[int]]:
    candidates = random.sample(list(nodes.keys()), k=min(6, len(nodes)))
    best_server = None
    best_span = -1
    for c in candidates:
        d = bfs_distances(nodes, c)
        span = max(d.values())
        if span > best_span:
            best_span = span
            best_server = c

    server = best_server if best_server is not None else random.choice(list(nodes.keys()))
    nodes[server].server = True

    d_from_server = bfs_distances(nodes, server)
    by_dist = {}
    for nid, dist in d_from_server.items():
        by_dist.setdefault(dist, []).append(nid)
    candidate_dists = sorted(by_dist.keys())
    chosen_starts = []
    for dist_val in candidate_dists[::-1]:
        pool = [n for n in by_dist[dist_val] if n != server]
        random.shuffle(pool)
        while pool and len(chosen_starts) < num_players:
            nid = pool.pop()
            if nid not in chosen_starts:
                chosen_starts.append(nid)
        if len(chosen_starts) == num_players:
            break
    if len(chosen_starts) < num_players:
        others = [n for n in nodes if n != server and n not in chosen_starts]
        random.shuffle(others)
        chosen_starts += others[: num_players - len(chosen_starts)]
    return server, chosen_starts

def shortest_path_next_step(nodes: Dict[int, Node], start: int, goal: int, pass_locked=True) -> Optional[int]:
    from collections import deque
    parent = {start: None}
    dq = deque([start])
    while dq:
        u = dq.popleft()
        if u == goal:
            break
        for v in nodes[u].neighbors:
            if v in parent:
                continue
            if not pass_locked and nodes[v].locked:
                continue
            parent[v] = u
            dq.append(v)
    if goal not in parent:
        return None
    cur = goal
    prev = parent[cur]
    while prev is not None and prev != start:
        cur = prev
        prev = parent[cur]
    return cur

# --------------------------- Terminal ---------------------------------
class Terminal:
    def __init__(self, capacity=400):
        self.lines: List[str] = []
        self.capacity = capacity
        self.input = ""
        self.cursor_visible = True
        self.cursor_timer = 0.0
        # new:
        self.scroll_offset = 0          # lines from bottom (0 = latest)
        self.history: List[str] = []
        self.history_index = -1         # -1 means editing current input
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.input = self.input[:-1]
            elif event.key == pygame.K_RETURN:
                line = self.input.strip()
                if line:
                    self.add("> " + line)
                    self.history.append(line)
                    self.history_index = -1
                    try:
                        if hasattr(self, "net"):
                            self.net.send_command(line)  # Send to server
                        else:
                            self.add("[Offline] No network connection.")
                    except Exception as e:
                        self.add(f"[Error sending command: {e}]")
                self.input = ""

            elif event.unicode and event.unicode.isprintable():
                self.input += event.unicode

    def add(self, text: str):
        for ln in text.splitlines():
            self.lines.append(ln)
        if len(self.lines) > self.capacity:
            overflow = len(self.lines) - self.capacity
            self.lines = self.lines[overflow:]
        # new output snaps view to bottom
        self.scroll_offset = 0

    def tick(self, dt: float):
        self.cursor_timer += dt
        if self.cursor_timer >= 0.5:
            self.cursor_timer = 0.0
            self.cursor_visible = not self.cursor_visible

    def scroll(self, lines: int):
        # lines positive => scroll down (towards newest), negative => older
        max_off = max(0, len(self.lines) - 1)
        self.scroll_offset = max(0, min(self.scroll_offset - lines, max_off))

    def recall_prev(self):
        if not self.history:
            return
        if self.history_index == -1:
            self.history_index = len(self.history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        self.input = self.history[self.history_index]

    def recall_next(self):
        if not self.history:
            return
        if self.history_index == -1:
            return
        self.history_index += 1
        if self.history_index >= len(self.history):
            self.history_index = -1
            self.input = ""
        else:
            self.input = self.history[self.history_index]

# ----------------------------- Chat Icon ------------------------------

class ChatToggleIcon:
    def __init__(self, x=20, y_offset=60):
        self.rect = pygame.Rect(x, H - y_offset, 44, 44)
        self.hover = False

    def draw(self, surf, chat_box):
        # Background
        bg_color = (45, 45, 60) if not self.hover else (70, 70, 100)
        pygame.draw.rect(surf, bg_color, self.rect, border_radius=10)

        # Chat bubble symbol
        color = (120, 200, 255) if not chat_box.visible else (180, 255, 180)
        x, y = self.rect.center
        pygame.draw.circle(surf, color, (x - 6, y - 6), 6)
        pygame.draw.circle(surf, color, (x + 6, y - 6), 6)
        pygame.draw.rect(surf, color, (x - 10, y - 3, 20, 8))
        pygame.draw.polygon(surf, color, [(x + 6, y + 8), (x + 1, y + 3), (x + 11, y + 3)])

    def handle_event(self, event, chat_box):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                chat_box.toggle()


# ----------------------------- Chat Platform --------------------------

class ChatBox:

    def __init__(self, width=380, height=180):
        self.width = width
        self.height = height
        self.visible = False
        self.messages = []
        self.input_text = ""
        self.font = pygame.font.SysFont("Consolas", 18)
        self.bot_reply_delay = 0
        self.pending_message = None

    def toggle(self):
        self.visible = not self.visible

    def handle_event(self, event):
        if not self.visible:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                text = self.input_text.strip()
                if text:
                    self.add_message("You", text)
                    self.pending_message = text
                    self.input_text = ""
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.toggle()
            else:
                if len(event.unicode) == 1:
                    self.input_text += event.unicode

    def update(self):
        if not self.visible:
            return
        if self.pending_message:
            self.bot_reply_delay += 1
            if self.bot_reply_delay > 30:
                reply = self.generate_reply(self.pending_message)
                self.add_message("Bot", reply)
                self.pending_message = None
                self.bot_reply_delay = 0

    def generate_reply(self, msg):
        msg = msg.lower()
        if "hello" in msg:
            return "Hey there, hacker!"
        elif "help" in msg:
            return "Try scanning or unlocking nodes first."
        elif "who" in msg:
            return "I’m your chat assistant — more features coming soon!"
        else:
            return "Interesting... continue."

    def add_message(self, sender, text):
        self.messages.append((sender, text))
        self.messages = self.messages[-8:]  # keep recent

    def wraplines(self, text, font, maxw):
        words = text.split()
        lines, cur = [], ""
        for w in words:
            test = cur + " " + w if cur else w
            if font.size(test)[0] > maxw:
                if cur:
                    lines.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
        return lines

    def draw(self, surf):
        if not self.visible:
            return

        x, y = 20, H - self.height - 20
        rect = pygame.Rect(x, y, self.width, self.height)
        pygame.draw.rect(surf, (25, 25, 35), rect)
        pygame.draw.rect(surf, (90, 90, 120), rect, 2)

        # messages
        offset_y = y + 10
        for sender, text in self.messages:
            color = (120, 200, 255) if sender == "You" else (180, 255, 180)
            bubble_text = f"{sender}: {text}"
            wrapped_lines = self.wraplines(bubble_text, self.font, self.width - 20)
            for line in wrapped_lines:
                surf.blit(self.font.render(line, True, color), (x + 10, offset_y))
                offset_y += 22

        # input line
        input_rect = pygame.Rect(x + 10, rect.bottom - 28, rect.w - 20, 20)
        pygame.draw.rect(surf, (40, 40, 55), input_rect)
        text_surface = self.font.render(self.input_text, True, (255, 255, 255))
        surf.blit(text_surface, (input_rect.x + 5, input_rect.y + 2))


        # input line
        input_rect = pygame.Rect(x + 10, rect.bottom - 28, rect.w - 20, 20)
        pygame.draw.rect(surf, (40, 40, 55), input_rect)
        text_surface = self.font.render(self.input_text, True, (255, 255, 255))
        surf.blit(text_surface, (input_rect.x + 5, input_rect.y + 2))

# --------------------------- AI logic ---------------------------------

class RivalAI:
    def __init__(self, player: Player):
        self.p = player
        self.cooldown = random.uniform(*AI_MOVE_COOLDOWN)

    def update(self, gs: GameState, dt: float, now: float):
        if not self.p.alive or gs.winner:
            return
        if now < self.p.stunned_until:
            return
        self.cooldown -= dt
        if self.cooldown > 0:
            return
        self.cooldown = random.uniform(*AI_MOVE_COOLDOWN)

        next_step = shortest_path_next_step(gs.nodes, self.p.current, gs.server_id, pass_locked=True)
        if next_step is None:
            if gs.nodes[self.p.current].neighbors:
                next_step = random.choice(list(gs.nodes[self.p.current].neighbors))
            else:
                return

        target_node = gs.nodes[next_step]
        if target_node.locked and next_step not in gs.global_unlocks:
            # try guess sometimes
            if random.random() < 0.18 and target_node.lock_pw:
                guess = ''.join(random.choice(string.ascii_lowercase) for _ in range(4))
                if guess == target_node.lock_pw:
                    gs.global_unlocks.add(next_step)
                    gs.log.append(f"{self.p.name} guessed and unlocked node {next_step}.")
            return

        self.p.current = next_step
        self.p.discovered.add(next_step)

        if next_step == gs.server_id:
            gs.winner = self.p.name
            gs.log.append(f"{self.p.name} hacked the server. Ship shuts down!")
            return

        if next_step in gs.traps and gs.traps[next_step] > 0:
            self.p.stunned_until = pygame.time.get_ticks()/1000.0 + STUN_TIME
            gs.traps[next_step] -= 1

        if target_node.mine:
            self.p.stunned_until = pygame.time.get_ticks()/1000.0 + STUN_TIME
            target_node.mine = False

# --------------------------- Commands ---------------------------------

BOOKLET_TEXT = [
    "help — list commands",
    "status — your node, distance to server, effects",
    "scan — reveal neighbors of your current node",
    "move <id> — move to adjacent node (if unlocked)",
    "path <id> — shortest path length (if known)",
    "reveal — temporarily reveal opponent moves for 5 seconds",
    "collect — collect any password if present in the node",
    "recon <id> — hint (scrambled) to locked node password",
    "unlock <id> <abc> — unlock locked node with 3-letter password",
    "trap — place a one-time stun trap on your current node",
    "decoy — spawn an untrustworthy virtual node (AI bait)",
    "quit — exit game",
]

def cmd_help(gs: GameState, player: Player, term: Terminal, args):
    term.add("Available commands:")
    for ln in BOOKLET_TEXT:
        term.add(ln)


def cmd_status(gs: GameState, player: Player, term: Terminal, *a):
    cur = player.current
    dist_map = bfs_distances(gs.nodes, cur)
    d = dist_map.get(gs.server_id, None)
    eff = []
    now = pygame.time.get_ticks()/1000.0
    if now < player.stunned_until:
        eff.append(f"STUNNED {player.stunned_until - now:.1f}s")
    term.add(f"At node {cur}. Distance to server: {d if d is not None else '?'} steps. " +
             (f"Effects: {', '.join(eff)}." if eff else "No effects."))
    neigh = sorted(gs.nodes[cur].neighbors)
    term.add(f"Neighbors: {', '.join(map(str, neigh)) if neigh else '(none)'}")
    term.add(f"Traps left: {player.traps_left} | Decoys left: {player.decoys_left}")

def cmd_scan(gs: GameState, player: Player, term: Terminal, *a):
    cur = player.current
    player.discovered.add(cur)
    if HUMAN_SCAN_REVEAL_NEIGHBORS:
        for nb in gs.nodes[cur].neighbors:
            player.discovered.add(nb)
    term.add("Scan complete. Nearby connections updated.")

def cmd_move(gs: GameState, player: Player, term: Terminal, args):
    now = pygame.time.get_ticks()/1000.0
    if now < player.stunned_until:
        term.add("You are stunned and cannot move.")
        return
    if not args:
        term.add("Usage: move <node_id>")
        return
    try:
        target = int(args[0])
    except ValueError:
        term.add("Node id must be an integer.")
        return
    cur = player.current
    if target not in gs.nodes[cur].neighbors:
        term.add(f"Node {target} is not adjacent to {cur}.")
        return
    node = gs.nodes[target]
    if node.locked and target not in gs.global_unlocks:
        term.add(f"Node {target} is locked. Unlock first.")
        return
    player.current = target
    player.discovered.add(target)
    term.add(f"Moved to node {target}.")
    if target == gs.server_id:
        gs.winner = player.name
        gs.log.append(f"{player.name} hacked the server.")
        term.add(">> SERVER HACKED! You win. <<")
        return
    if target in gs.traps and gs.traps[target] > 0:
        term.add("You triggered a trap! Stunned.")
        player.stunned_until = now + STUN_TIME+2
        gs.traps[target] -= 1
    if node.mine:
        term.add("You hit a mine! Stunned.")
        player.stunned_until = now + STUN_TIME
        node.mine = False

def cmd_path(gs: GameState, player: Player, term: Terminal, args):
    if not args:
        term.add("Usage: path <node_id>")
        return
    try:
        target = int(args[0])
    except ValueError:
        term.add("Node id must be an integer.")
        return
    if target not in gs.nodes:
        term.add("No such node.")
        return
    dist = bfs_distances(gs.nodes, player.current).get(target)
    if dist is None:
        term.add("Path unknown.")
    else:
        term.add(f"Shortest path length: {dist} step(s).")
def cmd_reveal(gs: GameState, player: Player, term: Terminal, *a):
    """
    Temporarily shows the positions of opponents and their movement.
    Only shows undiscovered nodes of opponents for 5 seconds.
    Can only be used 3 times per player.
    """
    # Initialize counter if not present
    if not hasattr(player, 'reveal_uses'):
        player.reveal_uses = 0

    # Check limit
    if player.reveal_uses >= 3:
        term.add("Reveal has already been used 3 times. Cannot use anymore.")
        return

    player.reveal_uses += 1
    term.add(f"Revealing opponents' positions for 5 seconds... (Use {player.reveal_uses}/3)")

    # Collect nodes to reveal: all nodes opponents are currently on
    reveal_nodes = set()
    for p in gs.players:
        if not p.is_human and p.alive:
            reveal_nodes.add(p.current)
            reveal_nodes.update(gs.nodes[p.current].neighbors)  # show moves

    # Save previous discovered state
    saved_discovered = {p.name: set(p.discovered) for p in gs.players}

    # Temporarily mark revealed nodes as discovered
    human = next(p for p in gs.players if p.is_human)
    human.discovered.update(reveal_nodes)

    # Hide them after 5 seconds
    def hide_revealed():
        pygame.time.wait(5000)
        human.discovered = saved_discovered[human.name]

    threading.Thread(target=hide_revealed, daemon=True).start()
def cmd_collect(gs: GameState, player: Player, term: Terminal, *args):
    """Collect a password from the current node, if available."""
    cur = player.current
    node = gs.nodes.get(cur)
    if not node:
        term.add("Current node not found.")
        return

    if getattr(node, "collect_pw", None):  # Check if node has a password to collect
        player.collected_pwds[cur] = node.collect_pw
        term.add(f"Collected password '{node.collect_pw}' from node {cur}.")
        node.collect_pw = None  # Remove after collecting
        gs.log.append(f"{player.name} collected password from node {cur}.")
    else:
        term.add("No password to collect at this node.")

def cmd_recon(gs: GameState, player: Player, term: Terminal, args):
    if not args:
        term.add("Usage: recon <node_id>")
        return
    try:
        nid = int(args[0])
    except ValueError:
        term.add("Node id must be an integer.")
        return
    if nid not in gs.nodes:
        term.add("No such node.")
        return
    n = gs.nodes[nid]
    if not n.locked or not n.lock_pw:
        term.add("That node is not locked.")
        return
    scrambled = ''.join(random.sample(n.lock_pw, k=len(n.lock_pw)))
    term.add(f"Recon: password letters are {scrambled} (scrambled).")


def cmd_unlock(gs: GameState, player: Player, term: Terminal, args):
    if len(args) != 2:
        term.add("Usage: unlock <node_id> <password>")
        return

    try:
        nid = int(args[0])
    except ValueError:
        term.add("Node id must be an integer.")
        return

    guess = args[1].strip().lower()
    node = gs.nodes.get(nid)
    if not node:
        term.add("No such node.")
        return
    if not node.locked:
        term.add("Node is not locked.")
        return

    if node.lock_pw == guess:
        node.locked = False
        gs.global_unlocks.add(nid)
        term.add(f"Node {nid} unlocked successfully!")
        gs.log.append(f"{player.name} unlocked node {nid}.")
    else:
        term.add("Incorrect password. Node remains locked.")

def cmd_trap(gs: GameState, player: Player, term: Terminal, *a):
    if player.traps_left <= 0:
        term.add("No traps remaining.")
        return
    nid = player.current
    gs.traps[nid] = gs.traps.get(nid, 0) + 1
    player.traps_left -= 1
    term.add(f"Trap placed at node {nid}.")

def cmd_decoy(gs: GameState, player: Player, term: Terminal, *a):
    if player.decoys_left <= 0:
        term.add("No decoys remaining.")
        return
    new_id = max(gs.nodes.keys()) + 1
    decoy = Node(new_id, _rand_pos_in_map(), decoy=True)
    gs.nodes[new_id] = decoy
    gs.nodes[player.current].neighbors.add(new_id)
    decoy.neighbors.add(player.current)
    player.decoys_left -= 1
    term.add("Decoy deployed.")

def cmd_log(gs: GameState, player: Player, term: Terminal, args):
    term.add("Recent events:")
    for ln in gs.log[-10:]:
        term.add(" - " + ln)

COMMANDS = {
    "help": cmd_help,
    "status": cmd_status,
    "scan": cmd_scan,
    "move": cmd_move,
    "path": cmd_path,
    "reveal": cmd_reveal,
    "collect": cmd_collect,   # NEW
    "recon": cmd_recon,
    "unlock": cmd_unlock,
    "trap": cmd_trap,
    "decoy": cmd_decoy,
}

# --------------------------- Pygame app -------------------------------

def handle_command(line: str, gs: GameState, term: Terminal):
    parts = line.split()
    if not parts:
        return
    cmd = parts[0].lower()
    args = parts[1:]
    player = next(p for p in gs.players if p.is_human)

    if cmd == "quit":
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        return

    fn = COMMANDS.get(cmd)
    if fn is None:
        term.add("Unknown command. Type 'help'.")
        return

    try:
        # Most command functions expect (gs, player, term, args)
        fn(gs, player, term, args)
    except TypeError:
        # for older signatures
        fn(gs, term)
    except Exception as e:
        term.add(f"Command error: {e}")

def build_new_game() -> GameState:
    nodes = generate_graph()
    server, starts = choose_server_and_starts(nodes, 1 + NUM_AI)
    nodes[server].locked = False
    nodes[server].lock_pw = None

    players: List[Player] = []
    human = Player("You", True, starts[0])
    human.discovered.add(human.current)
    players.append(human)
    for i in range(NUM_AI):
        p = Player(f"AI-{i+1}", False, starts[i + 1])
        p.discovered.add(p.current)
        players.append(p)
    edges = set()
    for node in nodes.values():
        for n in node.neighbors:
            edges.add(tuple(sorted((node.id, n))))

    gs = GameState(nodes=nodes, edges=edges, server_id=server, players=players)
    return gs


def draw_text(surface, text, pos, font, color=FG, shadow=True):
    if shadow:
        s = font.render(text, True, (0,0,0))
        surface.blit(s, (pos[0]+1, pos[1]+1))
    img = font.render(text, True, color)
    surface.blit(img, pos)

def wrap_lines(text: str, font, max_w: int) -> List[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def main():
    global W, H, SIDEBAR_W, MAP_W

    # --- Initialization ---
    pygame.init()
    pygame.mixer.init()
    pygame.font.init()

    # --- Setup display ---
    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    pygame.display.set_caption("Cyber Hax")

    # --- Music ---
    def play_music(path, volume=0.6, loop=-1):
        pygame.mixer.music.stop()
        try:
            music_path = r"D:\Projects\Cyber\Cyber-Hax-v3\main_music.ogg"
            if os.path.exists(music_path):
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.set_volume(volume)
                pygame.mixer.music.play(loop)
                print("[Music] Playing:", music_path)
            else:
                print("[Music] File missing:", music_path)
        except Exception as e:
            print("[Music] Disabled:", e)

    play_music(r"D:\Projects\Cyber\Cyber-Hax-v4\main_music.ogg")

    # --- Fonts & Clock ---
    font = pygame.font.SysFont("consolas,menlo,monospace", FONT_SIZE)
    title_font = pygame.font.SysFont("consolas,menlo,monospace", TITLE_FONT_SIZE, bold=True)
    clock = pygame.time.Clock()

    # --- Chat & UI ---
    chat_box = ChatBox()
    chat_icon = ChatToggleIcon()

    # --- Game setup ---
    gs = build_new_game()
    term = Terminal(capacity=800)
    from network_client import NetworkClient
    term.net = NetworkClient(term)

    ais = [RivalAI(p) for p in gs.players if not p.is_human]
    particles = []
    booklet_scroll = 0

    term.add(">>> CYBER HAX – Network breach simulation <<<")
    term.add("Type 'help' for available commands.")
    term.add("Goal: reach and hack the SERVER node first.")

    # --- Intro typing state ---
    intro_index = 0
    intro_char_index = 0
    intro_last_time = pygame.time.get_ticks()
    INTRO_CHAR_DELAY = 12
    INTRO_LINE_PAUSE = 200
    intro_line_done_time = None
    typed_line = ""
    screen_mode = "intro"

    running = True
    while running:
    # =========================
    # EVENT HANDLING
    # =========================
        for event in pygame.event.get():
            # -----------------------------
            # System / Window Controls
            # -----------------------------
            if event.type == pygame.QUIT:
                running = False
                continue

            elif event.type == pygame.VIDEORESIZE:
                W, H = event.w, event.h
                MAP_W = W - SIDEBAR_W
                screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
                continue

            # -----------------------------
            # Intro Skipping
            # -----------------------------
            if screen_mode == "intro" and (event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN):
                screen_mode = "start"
                continue

            # -----------------------------
            # Chat Toggle (Ctrl Key)
            # -----------------------------
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_LCTRL, pygame.K_RCTRL):
                chat_box.toggle()
                continue  # prevent same event from reaching terminal

            # -----------------------------
            # Chat vs Terminal Input Focus
            # -----------------------------
            if chat_box.visible:
                # Chatbox active: route input only to chat
                chat_box.handle_event(event)
                # Skip rest of input logic
                continue
            else:
                # Chatbox closed: route input only to terminal
                if screen_mode == "game":
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_PAGEUP:
                            booklet_scroll = max(0, booklet_scroll - 120)
                        elif event.key == pygame.K_PAGEDOWN:
                            booklet_scroll += 120
                        elif event.key == pygame.K_UP:
                            term.recall_prev()
                        elif event.key == pygame.K_DOWN:
                            term.recall_next()
                        elif event.key == pygame.K_BACKSPACE:
                            term.input = term.input[:-1]
                        elif event.key == pygame.K_RETURN:
                            line = term.input.strip()
                            if line:
                                term.add("> " + line)
                                term.history.append(line)
                                term.history_index = -1
                                handle_command(line, gs, term)
                            term.input = ""
                        elif event.key == pygame.K_ESCAPE:
                            running = False
                        elif event.unicode and event.unicode.isprintable():
                            term.input += event.unicode

            # -----------------------------
            # Mouse / Scroll Events
            # -----------------------------
            if event.type == pygame.MOUSEBUTTONDOWN and screen_mode == "start":
                play_music("main_music.ogg")
                screen_mode = "game"

            elif event.type == pygame.MOUSEWHEEL and screen_mode == "game":
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    term.scroll(event.y * 3)
                else:
                    booklet_scroll = max(0, booklet_scroll - event.y * 28)

            # -----------------------------
            # Chat Icon Click Detection
            # -----------------------------
            chat_icon.handle_event(event, chat_box)

            # =========================
        # INTRO UPDATE & DRAW
        # =========================
        if screen_mode == "intro":
            now = pygame.time.get_ticks()
            if intro_index < len(INTRO_LINES):
                line = INTRO_LINES[intro_index]
                if intro_char_index < len(line):
                    if now - intro_last_time >= INTRO_CHAR_DELAY:
                        typed_line += line[intro_char_index]
                        intro_char_index += 1
                        intro_last_time = now
                else:
                    if intro_line_done_time is None:
                        intro_line_done_time = now
                    elif now - intro_line_done_time >= INTRO_LINE_PAUSE:
                        intro_index += 1
                        intro_char_index = 0
                        intro_line_done_time = None
                        typed_line = ""
            else:
                screen_mode = "start"

            # --- Draw intro ---
            screen.fill((45, 45, 60))
            y = 100
            font_intro = pygame.font.SysFont("consolas", 28, bold=True)
            for i in range(intro_index):
                draw_text(screen, INTRO_LINES[i], (80, y), font_intro, (0, 255, 200))
                y += 40
            if intro_index < len(INTRO_LINES):
                draw_text(screen, typed_line, (80, y), font_intro, (0, 255, 200))

            pygame.display.flip()
            clock.tick(60)
            continue

        # =========================
        # LOGIC UPDATE
        # =========================
        dt = clock.tick(FPS) / 1000.0
        now = pygame.time.get_ticks() / 1000.0

        if random.random() < 0.35:
            particles.append(Particle(random.randint(0, max(1, MAP_W - 1)), H - 10))

        for p in particles[:]:
            p.update()
            if p.alpha <= 0:
                particles.remove(p)

        if screen_mode == "game" and not gs.winner:
            for ai in ais:
                ai.update(gs, dt, now)

        term.tick(dt)
        chat_box.update()

        # =========================
        # DRAW EVERYTHING
        # =========================
        screen.fill(BG)

        for p in particles:
            p.draw(screen)

        if screen_mode == "start":
            draw_text(screen, "CYBER HAX", (W // 2 - 140, H // 2 - 80), title_font, ACCENT)
            draw_text(screen, "A terminal-driven race to breach the ship's server.",
                      (W // 2 - 300, H // 2 - 28), font, MUTED)
            draw_text(screen, "Press Enter / Space / Click to begin",
                      (W // 2 - 220, H // 2 + 40), font, MUTED)
        elif screen_mode == "game":
            draw_game(screen, font, title_font, gs, term, booklet_scroll, chat_box)

        chat_box.draw(screen)
        if not chat_box.visible:
            chat_icon.draw(screen, chat_box)

        pygame.display.flip()

    pygame.quit()
    sys.exit()
    
def draw_game(screen, font, title_font, gs: GameState, term: Terminal, booklet_scroll: int, chat_box: ChatSystem):
    # Panels
    map_rect = pygame.Rect(0, 0, MAP_W, H)
    booklet_h = int(H * 0.55)
    booklet_rect = pygame.Rect(MAP_W, 0, SIDEBAR_W, booklet_h)
    term_rect = pygame.Rect(MAP_W, booklet_h, SIDEBAR_W, H - booklet_h)

    pygame.draw.rect(screen, MAP_BG, map_rect)

    human = next(p for p in gs.players if p.is_human)
    disc = human.discovered

    # edges (draw only if both discovered)
    for a, b in gs.edges:
        if a in disc and b in disc:
            pa = gs.nodes[a].pos
            pb = gs.nodes[b].pos
            pygame.draw.line(screen, (150, 150, 200), pa, pb, EDGE_THICKNESS)

    # nodes (discovered)
    for nid in sorted(disc):
        node = gs.nodes.get(nid)
        if not node:
            continue
        x, y = node.pos
        if nid == human.current:
            pygame.draw.circle(screen, (40,120,200), (x,y), CURRENT_HALO, 1)
        col = FG
        r = NODE_RADIUS
        if node.server:
            col = SERVER_COL; r = SERVER_RADIUS
        elif node.locked and nid not in gs.global_unlocks:
            col = LOCKED_COL
        elif node.mine:
            col = MINE_COL
        pulse = pygame.time.get_ticks() / 300  # or another scale
        draw_node(screen, x, y, col, pulse)

        pygame.draw.circle(screen, (20,24,32), (x,y), r, 1)
        label = font.render(str(nid), True, (230,230,240))
        screen.blit(label, (x - label.get_width()//2, y - r - label.get_height()))
    chat_box.draw(screen)

    # draw the chat box
    chat_box.draw(screen)

    # Booklet (scrollable)
    pygame.draw.rect(screen, (20,24,32), booklet_rect)
    pygame.draw.rect(screen, (35,40,50), booklet_rect, 1)
    draw_text(screen, "Command Booklet", (booklet_rect.x + 12, booklet_rect.y + 10), title_font, ACCENT)
    scroll_area_h = booklet_rect.h - 60
    y = booklet_rect.y + 54 - booklet_scroll
    content_h = 0
    for ln in BOOKLET_TEXT:
        # Split command name and description
        if "—" in ln:
            cmd_part, desc_part = ln.split("—", 1)
            cmd_part = cmd_part.strip()
            desc_part = "—" + desc_part.strip()
        else:
            cmd_part, desc_part = ln, ""

        if booklet_rect.y + 40 <= y <= booklet_rect.bottom - 20:
            # Draw the command name in green
            draw_text(screen, "• " + cmd_part, (booklet_rect.x + 12, y), font, (0, 255, 120), shadow=False)
            # Draw the description in normal color right after it
            cmd_w = font.size("• " + cmd_part)[0]
            draw_text(screen, " " + desc_part, (booklet_rect.x + 12 + cmd_w, y), font, FG, shadow=False)

        y += font.get_height() + 6
        content_h += font.get_height() + 6

    # clamp booklet_scroll to content height
    if content_h > 0:
        max_scroll = max(0, content_h - scroll_area_h)
        booklet_scroll = max(0, min(booklet_scroll, max_scroll))
    # scrollbar
    if content_h > scroll_area_h:
        bar_h = max(20, int(scroll_area_h * (scroll_area_h / content_h)))
        bar_y = booklet_rect.y + 54 + int((booklet_scroll / max(1, content_h)) * scroll_area_h)
        pygame.draw.rect(screen, (60,70,90), (booklet_rect.right - 10, bar_y, 6, bar_h))

    # Terminal panel
    pygame.draw.rect(screen, (14,16,22), term_rect)
    pygame.draw.rect(screen, (35,40,50), term_rect, 1)
    draw_text(screen, "Terminal", (term_rect.x + 12, term_rect.y + 10), title_font, ACCENT)


    log_margin = 8
    input_h = font.get_height() + 14
    log_area = pygame.Rect(term_rect.x + log_margin, term_rect.y + 48,
                           term_rect.w - 2*log_margin, term_rect.h - 48 - input_h - 10)
    input_rect = pygame.Rect(term_rect.x + log_margin,
                             term_rect.bottom - input_h - 6,
                             term_rect.w - 2*log_margin, input_h)

    # build wrapped terminal lines
    wrap_w = log_area.w
    wrapped = []
    for ln in term.lines:
        wrapped += wrap_lines(ln, font, wrap_w)
    max_lines = log_area.h // (font.get_height() + 2)
    start_index = max(0, len(wrapped) - max_lines - term.scroll_offset)
    view = wrapped[start_index:start_index + max_lines]
    y = log_area.y
    for ln in view:
        draw_text(screen, ln, (log_area.x, y), font, FG, shadow=False)
        y += font.get_height() + 2

    # input box
    pygame.draw.rect(screen, (28,30,38), input_rect)
    pygame.draw.rect(screen, (60,70,90), input_rect, 1)
    cursor = "_" if term.cursor_visible else " "
    disp = term.input + cursor
    draw_text(screen, disp, (input_rect.x + 8, input_rect.y + 6), font, FG, shadow=False)

    # Footer/winner banner
    if gs.winner:
        banner = f"{gs.winner} has hacked the server! Press ESC to quit."
        bimg = title_font.render(banner, True, DANGER)
        screen.blit(bimg, (MAP_W//2 - bimg.get_width()//2, 12))

# --------------------------- Entry point ------------------------------

if __name__ == "__main__":
    main()