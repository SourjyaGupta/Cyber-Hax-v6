# cyber_hax.py
# Cyber Hax – playable prototype with scrollable booklet & terminal + command history
# Compatible: Python 3.13, pygame 2.6.1

import random
import string
import sys
import argparse
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import threading
import math
import pygame
import datetime
import os
import time as pytime
from io import StringIO

import asyncio, websockets, threading, json

from game_core import (
    BOOKLET_TEXT as CORE_BOOKLET_TEXT,
    add_human_player,
    advance_game as advance_shared_game,
    build_new_game as build_shared_game,
    deserialize_state as deserialize_network_state,
    handle_command as handle_shared_command,
)

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
    glow = int((math.sin(pulse) + 1.0) * 10)
    outer_radius = 26 + glow
    glow_surface = pygame.Surface((outer_radius * 2, outer_radius * 2), pygame.SRCALPHA)
    center = (outer_radius, outer_radius)
    pygame.draw.circle(glow_surface, (*color, 28), center, outer_radius)
    pygame.draw.circle(glow_surface, (*color, 62), center, 16 + glow // 2)
    screen.blit(glow_surface, (x - outer_radius, y - outer_radius))
    pygame.draw.circle(screen, (250, 253, 255), (x, y), 14)
    pygame.draw.circle(screen, color, (x, y), 11)
    pygame.draw.circle(screen, PANEL_ALT, (x, y), 5)

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

NODE_COUNT = 16
EXTRA_EDGES = 8
MINE_RATIO = 0.08
LOCK_RATIO = 0.12

NUM_AI = 0
STUN_TIME = 6
AI_MOVE_COOLDOWN = (1.25, 2.2)
HUMAN_SCAN_REVEAL_NEIGHBORS = True
TRAP_LIMIT = 3
DECOY_LIMIT = 3
FONT_SIZE = 18
TITLE_FONT_SIZE = 36

NODE_RADIUS = 12
SERVER_RADIUS = 16
CURRENT_HALO = 24
EDGE_THICKNESS = 4

BG = (7, 12, 24)
MAP_BG = (11, 22, 42)
FG = (236, 244, 255)
MUTED = (145, 161, 188)
ACCENT = (90, 233, 255)
ACCENT_SOFT = (23, 74, 116)
WARN = (255, 196, 92)
DANGER = (255, 110, 135)
LOCKED_COL = (255, 194, 99)
MINE_COL = (255, 102, 138)
SERVER_COL = (112, 255, 196)
PANEL = (15, 26, 48)
PANEL_ALT = (10, 20, 39)
CARD = (21, 34, 60)
BORDER = (64, 101, 151)
INPUT_BG = (9, 17, 31)
EDGE_COL = (72, 122, 198)
GRID_COL = (24, 42, 72)
HILITE = (255, 255, 255)
SCANLINE = (255, 255, 255, 6)
CRT_BLOOM = (120, 204, 255, 20)
GLOW_A = (79, 156, 255)
GLOW_B = (23, 233, 215)
GLOW_C = (255, 118, 165)

FIELD_ORDER = ("player", "session", "server")


@dataclass
class ConnectionFormState:
    player: str
    session: str
    server: str
    active_field: str = "player"
    notice: str = "Set the host, shared room, and your callsign, then connect."


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
        self.x = x
        self.y_offset = y_offset
        self.rect = pygame.Rect(x, H - y_offset, 44, 44)
        self.hover = False

    def sync_rect(self):
        self.rect = pygame.Rect(self.x, H - self.y_offset, 44, 44)

    def draw(self, surf, chat_box):
        self.sync_rect()
        bg_color = CARD if not self.hover else PANEL
        pygame.draw.rect(surf, bg_color, self.rect, border_radius=14)
        pygame.draw.rect(surf, BORDER, self.rect, 1, border_radius=14)

        color = HILITE if not chat_box.visible else ACCENT
        x, y = self.rect.center
        pygame.draw.circle(surf, color, (x - 6, y - 6), 6)
        pygame.draw.circle(surf, color, (x + 6, y - 6), 6)
        pygame.draw.rect(surf, color, (x - 10, y - 3, 20, 8))
        pygame.draw.polygon(surf, color, [(x + 6, y + 8), (x + 1, y + 3), (x + 11, y + 3)])

    def handle_event(self, event, chat_box):
        self.sync_rect()
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
        self.font = pygame.font.SysFont("segoeui", 17)
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
        draw_panel(surf, rect, fill=PANEL, border=BORDER, radius=18)

        # messages
        offset_y = y + 10
        for sender, text in self.messages:
            color = HILITE if sender == "You" else ACCENT
            bubble_text = f"{sender}: {text}"
            wrapped_lines = self.wraplines(bubble_text, self.font, self.width - 20)
            for line in wrapped_lines:
                surf.blit(self.font.render(line, True, color), (x + 10, offset_y))
                offset_y += 22

        # input line
        input_rect = pygame.Rect(x + 10, rect.bottom - 28, rect.w - 20, 20)
        draw_panel(surf, input_rect, fill=INPUT_BG, border=BORDER, radius=10)
        text_surface = self.font.render(self.input_text, True, FG)
        surf.blit(text_surface, (input_rect.x + 5, input_rect.y + 2))


        # input line
        input_rect = pygame.Rect(x + 10, rect.bottom - 28, rect.w - 20, 20)
        draw_panel(surf, input_rect, fill=INPUT_BG, border=BORDER, radius=10)
        text_surface = self.font.render(self.input_text, True, FG)
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


def mix_color(start, end, amount):
    amount = max(0.0, min(1.0, amount))
    return tuple(int(start[i] + (end[i] - start[i]) * amount) for i in range(3))


def fit_text(text, font, max_width):
    if font.size(text)[0] <= max_width:
        return text
    shortened = text
    while shortened and font.size(shortened + "...")[0] > max_width:
        shortened = shortened[:-1]
    return (shortened + "...") if shortened else "..."


def draw_vertical_gradient(surface, rect, top_color, bottom_color):
    height = max(1, rect.h)
    gradient = pygame.Surface((1, height))
    for y in range(height):
        gradient.set_at((0, y), mix_color(top_color, bottom_color, y / max(1, height - 1)))
    surface.blit(pygame.transform.scale(gradient, (rect.w, height)), rect.topleft)


def draw_panel(surface, rect, fill=PANEL, border=BORDER, radius=18):
    shadow = pygame.Surface((rect.w + 18, rect.h + 18), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 70), shadow.get_rect(), border_radius=radius + 6)
    surface.blit(shadow, (rect.x - 9, rect.y + 8))

    panel = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (*fill, 238), panel.get_rect(), border_radius=radius)
    pygame.draw.rect(panel, (*border, 255), panel.get_rect(), 1, border_radius=radius)
    surface.blit(panel, rect.topleft)


def draw_chip(surface, font, text, pos, fill=CARD, border=BORDER, color=FG):
    pad_x = 12
    pad_y = 7
    text_img = font.render(text, True, color)
    rect = pygame.Rect(pos[0], pos[1], text_img.get_width() + pad_x * 2, text_img.get_height() + pad_y * 2)
    draw_panel(surface, rect, fill=fill, border=border, radius=999)
    surface.blit(text_img, (rect.x + pad_x, rect.y + pad_y))
    return rect


def draw_input_field(surface, rect, label, value, font, small_font, active=False, hovered=False, placeholder=""):
    border = ACCENT if active else (mix_color(BORDER, HILITE, 0.32) if hovered else BORDER)
    fill = mix_color(INPUT_BG, CARD, 0.22 if active else 0.0)
    draw_panel(surface, rect, fill=fill, border=border, radius=18)
    draw_text(surface, label.upper(), (rect.x + 16, rect.y + 10), small_font, MUTED, shadow=False)
    display = value or placeholder
    display = fit_text(display, font, rect.w - 30)
    color = FG if value else MUTED
    draw_text(surface, display, (rect.x + 16, rect.y + 30), font, color, shadow=False)
    if active:
        cursor_x = rect.x + 18 + min(rect.w - 38, font.size(display)[0])
        pygame.draw.line(surface, ACCENT, (cursor_x, rect.y + 30), (cursor_x, rect.bottom - 12), 2)


def draw_action_button(surface, rect, label, font, hovered=False, primary=False):
    fill = mix_color(ACCENT_SOFT, ACCENT, 0.40 if primary else 0.14)
    if hovered:
        fill = mix_color(fill, HILITE, 0.18)
    border = ACCENT if primary else BORDER
    text_color = FG if not primary else PANEL_ALT
    draw_panel(surface, rect, fill=fill, border=border, radius=18)
    text = font.render(label, True, text_color)
    surface.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))


def refresh_layout(width=None, height=None):
    global W, H, SIDEBAR_W, MAP_W
    if width is not None:
        W = max(1100, width)
    if height is not None:
        H = max(700, height)
    SIDEBAR_W = max(390, min(500, int(W * 0.36)))
    MAP_W = W - SIDEBAR_W


def draw_scanlines(surface):
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    for y in range(0, H, 5):
        pygame.draw.line(overlay, SCANLINE, (0, y), (W, y))
    pygame.draw.rect(overlay, CRT_BLOOM, (0, 0, W, H), 1)
    surface.blit(overlay, (0, 0))


def get_connection_button_rect():
    return pygame.Rect(MAP_W - 188, 18, 170, 40)


def build_start_screen_layout():
    frame = pygame.Rect(42, 42, W - 84, H - 84)
    left_w = int(frame.w * 0.48)
    left = pygame.Rect(frame.x + 24, frame.y + 24, left_w - 18, frame.h - 48)
    right = pygame.Rect(left.right + 22, frame.y + 24, frame.right - left.right - 46, frame.h - 48)
    return {
        "frame": frame,
        "left": left,
        "right": right,
        "status": pygame.Rect(left.x + 20, left.y + 126, left.w - 40, 48),
        "player": pygame.Rect(left.x + 20, left.y + 196, left.w - 40, 60),
        "session": pygame.Rect(left.x + 20, left.y + 272, left.w - 40, 60),
        "server": pygame.Rect(left.x + 20, left.y + 348, left.w - 40, 60),
        "connect": pygame.Rect(left.x + 20, left.y + 432, left.w - 40, 54),
        "resume": pygame.Rect(left.x + 20, left.y + 498, left.w - 40, 48),
        "preview": pygame.Rect(right.x + 18, right.y + 20, right.w - 36, int(right.h * 0.54)),
        "tips": pygame.Rect(right.x + 18, right.y + 20 + int(right.h * 0.54) + 18, right.w - 36, right.h - int(right.h * 0.54) - 56),
    }


def connection_status_summary(network_client):
    if network_client is None:
        return "Standby - choose a host and connect.", MUTED
    if network_client.connected:
        return "Linked - session live.", ACCENT
    if getattr(network_client, "status", "") in ("connecting", "reconnecting"):
        return "Dialing server...", WARN
    if getattr(network_client, "last_error", ""):
        return "Last link attempt failed - edit the host or wait for retry.", DANGER
    return "Preparing connection...", MUTED


def draw_preview_map(surface, rect, gs, viewer_name):
    draw_panel(surface, rect, fill=PANEL, border=BORDER, radius=24)
    draw_text(surface, "Arena Preview", (rect.x + 18, rect.y + 16), pygame.font.SysFont("consolas", 20, bold=True), ACCENT, shadow=False)

    if not gs.nodes:
        return

    min_x = min(node.pos[0] for node in gs.nodes.values())
    max_x = max(node.pos[0] for node in gs.nodes.values())
    min_y = min(node.pos[1] for node in gs.nodes.values())
    max_y = max(node.pos[1] for node in gs.nodes.values())
    usable = pygame.Rect(rect.x + 18, rect.y + 54, rect.w - 36, rect.h - 72)

    def map_point(pos):
        x_span = max(1, max_x - min_x)
        y_span = max(1, max_y - min_y)
        px = usable.x + int(((pos[0] - min_x) / x_span) * usable.w)
        py = usable.y + int(((pos[1] - min_y) / y_span) * usable.h)
        return px, py

    for edge_a, edge_b in gs.edges:
        pa = map_point(gs.nodes[edge_a].pos)
        pb = map_point(gs.nodes[edge_b].pos)
        pygame.draw.line(surface, mix_color(EDGE_COL, HILITE, 0.22), pa, pb, 2)

    viewer = next((player for player in gs.players if player.name == viewer_name), None)
    for node_id, node in gs.nodes.items():
        x, y = map_point(node.pos)
        color = FG
        radius = 7
        if node.server:
            color = SERVER_COL
            radius = 10
        elif node.locked:
            color = LOCKED_COL
        elif node.mine:
            color = MINE_COL
        pygame.draw.circle(surface, color, (x, y), radius)
        if viewer is not None and node_id == viewer.current:
            pygame.draw.circle(surface, HILITE, (x, y), radius + 6, 2)


def find_hovered_node(gs, visible_nodes, mouse_pos):
    if mouse_pos[0] > MAP_W:
        return None
    hovered = None
    best_dist = 999999
    for node_id in visible_nodes:
        node = gs.nodes.get(node_id)
        if not node:
            continue
        dx = mouse_pos[0] - node.pos[0]
        dy = mouse_pos[1] - node.pos[1]
        dist_sq = dx * dx + dy * dy
        if dist_sq <= (CURRENT_HALO + 12) ** 2 and dist_sq < best_dist:
            hovered = node_id
            best_dist = dist_sq
    return hovered


def draw_hover_tooltip(screen, font, small_font, mouse_pos, title, lines, accent):
    wrapped = []
    for line in lines:
        wrapped.extend(wrap_lines(line, small_font, 240))
    width = 266
    height = 18 + font.get_height() + len(wrapped) * (small_font.get_height() + 4) + 18
    x = min(mouse_pos[0] + 18, W - width - 16)
    y = min(mouse_pos[1] + 18, H - height - 16)
    rect = pygame.Rect(x, y, width, height)
    draw_panel(screen, rect, fill=PANEL, border=accent, radius=16)
    draw_text(screen, title, (rect.x + 14, rect.y + 10), font, accent, shadow=False)
    text_y = rect.y + 18 + font.get_height()
    for line in wrapped:
        draw_text(screen, line, (rect.x + 14, text_y), small_font, FG, shadow=False)
        text_y += small_font.get_height() + 4


def draw_start_screen(screen, font, small_font, title_font, form, gs, mouse_pos, network_client, can_resume):
    screen.fill(BG)
    draw_vertical_gradient(screen, screen.get_rect(), BG, MAP_BG)
    pulse = pygame.time.get_ticks() / 1000.0
    pygame.draw.circle(screen, (*GLOW_A, 24), (W - 120, 120), 120, 1)
    pygame.draw.circle(screen, (*GLOW_B, 24), (110, H - 120), 160, 1)
    draw_panel(screen, build_start_screen_layout()["frame"], fill=PANEL_ALT, border=BORDER, radius=30)

    layout = build_start_screen_layout()
    left = layout["left"]
    right = layout["right"]
    draw_panel(screen, left, fill=PANEL, border=BORDER, radius=26)
    draw_panel(screen, right, fill=PANEL_ALT, border=BORDER, radius=26)

    draw_text(screen, "CYBER HAX", (left.x + 20, left.y + 24), title_font, ACCENT, shadow=False)
    draw_text(screen, "Neon relay duel", (left.x + 24, left.y + 70), font, FG, shadow=False)
    draw_text(
        screen,
        "Clean two-player infiltration. Connect to a friend, share a room name, and race to the core.",
        (left.x + 24, left.y + 98),
        small_font,
        MUTED,
        shadow=False,
    )

    status_text, status_color = connection_status_summary(network_client)
    draw_panel(screen, layout["status"], fill=CARD, border=status_color, radius=18)
    draw_text(screen, status_text, (layout["status"].x + 14, layout["status"].y + 14), small_font, status_color, shadow=False)

    hover_player = layout["player"].collidepoint(mouse_pos)
    hover_session = layout["session"].collidepoint(mouse_pos)
    hover_server = layout["server"].collidepoint(mouse_pos)
    draw_input_field(screen, layout["player"], "Callsign", form.player, font, small_font, form.active_field == "player", hover_player, "Operator-101")
    draw_input_field(screen, layout["session"], "Shared room", form.session, font, small_font, form.active_field == "session", hover_session, "session1")
    draw_input_field(screen, layout["server"], "Server host", form.server, font, small_font, form.active_field == "server", hover_server, "ws://127.0.0.1:8000")

    draw_action_button(screen, layout["connect"], "Connect To Server", font, layout["connect"].collidepoint(mouse_pos), primary=True)
    if can_resume:
        draw_action_button(screen, layout["resume"], "Resume Mission", font, layout["resume"].collidepoint(mouse_pos), primary=False)

    draw_text(
        screen,
        form.notice,
        (left.x + 24, left.bottom - 48),
        small_font,
        MUTED,
        shadow=False,
    )

    draw_preview_map(screen, layout["preview"], gs, form.player)
    draw_panel(screen, layout["tips"], fill=PANEL, border=BORDER, radius=22)
    draw_text(screen, "How To Join", (layout["tips"].x + 16, layout["tips"].y + 14), font, WARN, shadow=False)
    tips = [
        "Host runs the server and shares the public IP with the other player.",
        "Both players use the same room name so they land in the same match.",
        "You can paste either ws://HOST:8000 or a full /ws/room path - the game will normalize it.",
        "Press F2 during a match to reopen these network settings.",
    ]
    tip_y = layout["tips"].y + 48
    for tip in tips:
        for line in wrap_lines(tip, small_font, layout["tips"].w - 28):
            draw_text(screen, line, (layout["tips"].x + 16, tip_y), small_font, FG, shadow=False)
            tip_y += small_font.get_height() + 5
        tip_y += 8


def cycle_connection_field(form, direction=1):
    index = FIELD_ORDER.index(form.active_field)
    form.active_field = FIELD_ORDER[(index + direction) % len(FIELD_ORDER)]


def normalize_server_base(server_value):
    server = server_value.strip() or "ws://127.0.0.1:8000"
    if server.startswith("http://"):
        server = "ws://" + server[len("http://") :]
    elif server.startswith("https://"):
        server = "wss://" + server[len("https://") :]
    elif "://" not in server:
        server = "ws://" + server
    server = server.rstrip("/")
    if "/ws/" in server:
        server = server.split("/ws/", 1)[0]
    return server


def parse_runtime_options():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--session", default=os.environ.get("CYBER_HAX_SESSION", "session1"))
    parser.add_argument("--player", default=os.environ.get("CYBER_HAX_PLAYER"))
    parser.add_argument(
        "--server",
        default=os.environ.get("CYBER_HAX_SERVER", "ws://127.0.0.1:8000"),
    )
    args = parser.parse_args()
    if not args.player:
        args.player = f"Operator-{random.randint(100, 999)}"
    return args

def main():
    global W, H, SIDEBAR_W, MAP_W
    runtime = parse_runtime_options()
    connection_form = ConnectionFormState(
        player=runtime.player,
        session=runtime.session,
        server=normalize_server_base(runtime.server),
    )
    project_dir = os.path.dirname(os.path.abspath(__file__))
    refresh_layout(W, H)

    pygame.init()
    pygame.mixer.init()
    pygame.font.init()

    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    pygame.display.set_caption("Cyber Hax - Neon Relay Duel")

    def play_music(path, volume=0.6, loop=-1):
        pygame.mixer.music.stop()
        try:
            music_path = os.path.join(project_dir, "main_music.ogg")
            if os.path.exists(music_path):
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.set_volume(volume)
                pygame.mixer.music.play(loop)
            else:
                print("[Music] File missing:", music_path)
        except Exception as e:
            print("[Music] Disabled:", e)

    play_music(os.path.join(project_dir, "main_music.ogg"), volume=0.38)

    font = pygame.font.SysFont("segoeui", FONT_SIZE + 1, bold=True)
    small_font = pygame.font.SysFont("segoeui", 16)
    term_font = pygame.font.SysFont("consolas", FONT_SIZE)
    title_font = pygame.font.SysFont("consolas", TITLE_FONT_SIZE, bold=True)
    clock = pygame.time.Clock()

    chat_box = ChatBox()
    chat_icon = ChatToggleIcon()

    term = Terminal(capacity=800)
    term.net = None
    from network_client import NetworkClient

    def build_preview_state(player_name):
        preview = build_shared_game(max_humans=2, num_ai=0)
        add_human_player(preview, player_name)
        return preview

    state_holder = {"gs": build_preview_state(connection_form.player), "player_name": connection_form.player}
    session_started = False

    def on_network_state(state_payload, assigned_name):
        state_holder["gs"] = deserialize_network_state(state_payload)
        if assigned_name:
            state_holder["player_name"] = assigned_name
            connection_form.player = assigned_name

    def connect_to_server():
        nonlocal session_started, screen_mode
        clean_player = " ".join(connection_form.player.strip().split()) or f"Operator-{random.randint(100, 999)}"
        clean_session = connection_form.session.strip().replace(" ", "-") or "session1"
        connection_form.player = clean_player[:24]
        connection_form.session = clean_session[:32]
        connection_form.server = normalize_server_base(connection_form.server)
        state_holder["gs"] = build_preview_state(connection_form.player)
        state_holder["player_name"] = connection_form.player
        if getattr(term, "net", None) is not None:
            term.net.close()
        term.net = NetworkClient(
            term,
            session_id=connection_form.session,
            player_name=connection_form.player,
            server_base=connection_form.server,
            state_callback=on_network_state,
        )
        session_started = True
        screen_mode = "game"
        connection_form.notice = "Press F2 anytime to update the host, room, or callsign."
        term.add("")
        term.add(f"[Network] Linking to {connection_form.server}/ws/{connection_form.session}")
        term.add(f"[Network] Callsign {connection_form.player}")

    particles = []
    booklet_scroll = 0

    term.add("CYBER HAX :: Neon Relay Duel")
    term.add("Open the launch screen, enter a host and room name, then connect.")
    term.add("Terminal opener: mission, status, sweep, hint, probe <id>.")

    screen_mode = "start"
    hovered_node = None

    running = True
    while running:
        gs = state_holder["gs"]
        mouse_pos = pygame.mouse.get_pos()
        net_client = getattr(term, "net", None)
        viewer = next(
            (player for player in gs.players if player.name == state_holder["player_name"]),
            next((player for player in gs.players if player.is_human), gs.players[0]),
        )
        visible_nodes = set(viewer.discovered) | set(getattr(viewer, "reveal_nodes", set()))
        hovered_node = find_hovered_node(gs, visible_nodes, mouse_pos)
        start_layout = build_start_screen_layout()
        connection_button_rect = get_connection_button_rect()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            elif event.type == pygame.VIDEORESIZE:
                refresh_layout(event.w, event.h)
                screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
                continue

            if screen_mode == "start":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_TAB:
                        cycle_connection_field(connection_form, -1 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        connect_to_server()
                    elif event.key == pygame.K_ESCAPE:
                        if session_started:
                            screen_mode = "game"
                        else:
                            running = False
                    elif event.key == pygame.K_BACKSPACE:
                        current_value = getattr(connection_form, connection_form.active_field)
                        setattr(connection_form, connection_form.active_field, current_value[:-1])
                    elif event.unicode and event.unicode.isprintable():
                        field_name = connection_form.active_field
                        limit = 96 if field_name == "server" else 32
                        current_value = getattr(connection_form, field_name)
                        setattr(connection_form, field_name, (current_value + event.unicode)[:limit])
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if start_layout["connect"].collidepoint(event.pos):
                        connect_to_server()
                    elif session_started and start_layout["resume"].collidepoint(event.pos):
                        screen_mode = "game"
                    else:
                        for field_name in FIELD_ORDER:
                            if start_layout[field_name].collidepoint(event.pos):
                                connection_form.active_field = field_name
                                break
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
                screen_mode = "start"
                connection_form.notice = "Update the host, room, or callsign, then reconnect."
                continue

            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and connection_button_rect.collidepoint(event.pos)
            ):
                screen_mode = "start"
                connection_form.notice = "Update the host, room, or callsign, then reconnect."
                continue

            if event.type == pygame.KEYDOWN and event.key in (pygame.K_LCTRL, pygame.K_RCTRL):
                chat_box.toggle()
                continue

            if chat_box.visible:
                chat_box.handle_event(event)
                continue

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
                        if net_client is not None and net_client.connected:
                            net_client.send_command(line)
                        else:
                            if line.lower() == "quit":
                                running = False
                            else:
                                output = StringIO()
                                handle_shared_command(
                                    line,
                                    gs,
                                    state_holder["player_name"],
                                    output,
                                    now=pytime.monotonic(),
                                )
                                for response_line in output.getvalue().splitlines():
                                    term.add(response_line)
                    term.input = ""
                elif event.key == pygame.K_ESCAPE:
                    running = False
                elif event.unicode and event.unicode.isprintable():
                    term.input += event.unicode

            if event.type == pygame.MOUSEWHEEL:
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    term.scroll(event.y * 3)
                else:
                    booklet_scroll = max(0, booklet_scroll - event.y * 28)
            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and not chat_box.visible
                and hovered_node is not None
            ):
                current_node = viewer.current
                if event.button == 1:
                    if hovered_node == current_node:
                        term.input = f"probe {hovered_node}"
                    elif hovered_node in gs.nodes[current_node].neighbors:
                        if gs.nodes[hovered_node].locked and hovered_node not in gs.global_unlocks:
                            term.input = f"probe {hovered_node}"
                        else:
                            term.input = f"move {hovered_node}"
                    else:
                        term.input = f"probe {hovered_node}"
                elif event.button == 3:
                    term.input = f"probe {hovered_node}"

            chat_icon.handle_event(event, chat_box)

        dt = clock.tick(FPS) / 1000.0
        gs = state_holder["gs"]

        if random.random() < 0.35:
            particles.append(Particle(random.randint(0, max(1, MAP_W - 1)), H - 10))

        for p in particles[:]:
            p.update()
            if p.alpha <= 0:
                particles.remove(p)

        if screen_mode == "game" and not gs.winner and (net_client is None or not net_client.connected):
            advance_shared_game(gs, now=pytime.monotonic())

        term.tick(dt)
        if screen_mode == "game":
            chat_box.update()

        draw_vertical_gradient(screen, screen.get_rect(), BG, MAP_BG)

        for p in particles:
            p.draw(screen)

        if screen_mode == "start":
            draw_start_screen(
                screen,
                font,
                small_font,
                title_font,
                connection_form,
                gs,
                mouse_pos,
                net_client,
                session_started,
            )
        elif screen_mode == "game":
            draw_game(
                screen,
                font,
                small_font,
                term_font,
                title_font,
                gs,
                term,
                booklet_scroll,
                chat_box,
                state_holder["player_name"],
                connection_form.session,
                getattr(net_client, "connected", False),
                hovered_node,
                mouse_pos,
            )
        draw_scanlines(screen)

        if screen_mode == "game":
            chat_box.draw(screen)
            if not chat_box.visible:
                chat_icon.draw(screen, chat_box)

        pygame.display.flip()

    if getattr(term, "net", None) is not None:
        term.net.close()
    pygame.quit()
    sys.exit()
    
def _legacy_draw_game(
    screen,
    font,
    title_font,
    gs: GameState,
    term: Terminal,
    booklet_scroll: int,
    chat_box: ChatSystem,
    viewer_name: str,
):
    # Panels
    map_rect = pygame.Rect(0, 0, MAP_W, H)
    booklet_h = int(H * 0.55)
    booklet_rect = pygame.Rect(MAP_W, 0, SIDEBAR_W, booklet_h)
    term_rect = pygame.Rect(MAP_W, booklet_h, SIDEBAR_W, H - booklet_h)

    pygame.draw.rect(screen, MAP_BG, map_rect)

    human = next(
        (player for player in gs.players if player.name == viewer_name),
        next((player for player in gs.players if player.is_human), gs.players[0]),
    )
    disc = set(human.discovered) | set(getattr(human, "reveal_nodes", set()))

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


def draw_game(
    screen,
    font,
    small_font,
    term_font,
    title_font,
    gs,
    term,
    booklet_scroll,
    chat_box,
    viewer_name,
    session_name,
    is_online,
    hovered_node,
    mouse_pos,
):
    map_rect = pygame.Rect(0, 0, MAP_W, H)
    mission_h = int(H * 0.44)
    mission_rect = pygame.Rect(MAP_W + 8, 10, SIDEBAR_W - 18, mission_h - 14)
    term_rect = pygame.Rect(MAP_W + 8, mission_rect.bottom + 10, SIDEBAR_W - 18, H - mission_rect.bottom - 18)

    draw_vertical_gradient(screen, map_rect, mix_color(MAP_BG, GLOW_A, 0.15), MAP_BG)
    t = pygame.time.get_ticks() / 1000.0
    for x in range(0, MAP_W, 54):
        shade = mix_color(GRID_COL, ACCENT, 0.12 + 0.08 * math.sin((x / 80.0) + t))
        pygame.draw.line(screen, shade, (x, 0), (x, H), 1)
    for y in range(0, H, 54):
        shade = mix_color(GRID_COL, GLOW_B, 0.06 + 0.05 * math.cos((y / 70.0) + t))
        pygame.draw.line(screen, shade, (0, y), (MAP_W, y), 1)
    for center, base_color, radius in (
        ((int(MAP_W * 0.18), int(H * 0.2)), GLOW_B, 110),
        ((int(MAP_W * 0.82), int(H * 0.28)), GLOW_A, 140),
        ((int(MAP_W * 0.58), int(H * 0.86)), GLOW_C, 160),
    ):
        glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*base_color, 22), (radius, radius), radius)
        screen.blit(glow, (center[0] - radius, center[1] - radius))

    human = next(
        (player for player in gs.players if player.name == viewer_name),
        next((player for player in gs.players if player.is_human), gs.players[0]),
    )
    disc = set(human.discovered) | set(getattr(human, "reveal_nodes", set()))
    now_monotonic = pytime.monotonic()
    distance_map = bfs_distances(gs.nodes, human.current)
    distance_to_server = distance_map.get(gs.server_id, "?")
    human_count = len([player for player in gs.players if player.is_human])
    other_humans = [player for player in gs.players if player.is_human and player.name != human.name]
    effects = []
    if getattr(human, "stunned_until", 0) > now_monotonic:
        effects.append("stunned")
    if getattr(human, "shield_until", 0) > now_monotonic:
        effects.append("shield")
    status_text = ", ".join(effects) if effects else "stable"

    hud_rect = pygame.Rect(18, 18, min(362, MAP_W - 220), 154)
    intel_rect = pygame.Rect(18, hud_rect.bottom + 14, min(362, MAP_W - 220), 108)
    legend_rect = pygame.Rect(18, H - 126, min(330, MAP_W - 220), 108)
    connection_rect = get_connection_button_rect()

    draw_panel(screen, hud_rect, fill=PANEL, border=BORDER, radius=24)
    draw_text(screen, human.name, (hud_rect.x + 18, hud_rect.y + 14), title_font, ACCENT, shadow=False)
    draw_text(screen, f"Current node {human.current}", (hud_rect.x + 18, hud_rect.y + 56), font, FG, shadow=False)
    draw_text(screen, f"Server node {gs.server_id}  |  Distance {distance_to_server}", (hud_rect.x + 18, hud_rect.y + 82), small_font, MUTED, shadow=False)
    draw_text(screen, f"Visible {len(disc)}/{len(gs.nodes)}  |  Status {status_text}", (hud_rect.x + 18, hud_rect.y + 104), small_font, FG, shadow=False)
    draw_text(screen, f"Sweeps {getattr(human, 'sweeps_left', 0)}  Patch {getattr(human, 'patch_kits', 0)}  Traps {human.traps_left}  Decoys {human.decoys_left}", (hud_rect.x + 18, hud_rect.y + 126), small_font, MUTED, shadow=False)
    draw_chip(
        screen,
        small_font,
        "ONLINE" if is_online else "OFFLINE",
        (hud_rect.right - 192, hud_rect.y + 16),
        fill=ACCENT_SOFT if is_online else CARD,
        color=FG,
    )
    draw_chip(
        screen,
        small_font,
        f"Session {session_name}",
        (hud_rect.right - 192, hud_rect.y + 54),
        fill=CARD,
        color=MUTED,
    )
    draw_action_button(screen, connection_rect, "F2 Link Settings", small_font, connection_rect.collidepoint(mouse_pos), primary=False)

    draw_panel(screen, intel_rect, fill=PANEL_ALT, border=BORDER, radius=22)
    rival_name = other_humans[0].name if other_humans else "Awaiting second operator"
    intel_lines = [
        f"Operators online: {human_count}/2",
        f"Rival: {rival_name}",
        "Hover any node for live intel. Left click to queue movement or a probe.",
    ]
    draw_text(screen, "Live Intel", (intel_rect.x + 16, intel_rect.y + 12), font, WARN, shadow=False)
    text_y = intel_rect.y + 42
    for line in intel_lines:
        for wrapped_line in wrap_lines(line, small_font, intel_rect.w - 26):
            draw_text(screen, wrapped_line, (intel_rect.x + 16, text_y), small_font, FG, shadow=False)
            text_y += small_font.get_height() + 4
        text_y += 4

    for a, b in gs.edges:
        if a in disc and b in disc:
            pa = gs.nodes[a].pos
            pb = gs.nodes[b].pos
            line_color = EDGE_COL
            thickness = EDGE_THICKNESS
            if hovered_node in (a, b) or human.current in (a, b):
                line_color = mix_color(ACCENT, HILITE, 0.35)
                thickness = EDGE_THICKNESS + 1
            pygame.draw.line(screen, line_color, pa, pb, thickness)
            signal_t = ((pygame.time.get_ticks() / 1300.0) + ((a + b) * 0.17)) % 1.0
            sx = pa[0] + (pb[0] - pa[0]) * signal_t
            sy = pa[1] + (pb[1] - pa[1]) * signal_t
            pygame.draw.circle(screen, ACCENT, (int(sx), int(sy)), 3)

    for nid in sorted(disc):
        node = gs.nodes.get(nid)
        if not node:
            continue
        x, y = node.pos
        if nid == human.current:
            pygame.draw.circle(screen, HILITE, (x, y), CURRENT_HALO + int(2 * math.sin(t * 5.0)), 2)
        if hovered_node == nid:
            pygame.draw.circle(screen, ACCENT, (x, y), CURRENT_HALO + 8, 2)
        col = FG
        r = NODE_RADIUS
        if node.server:
            col = SERVER_COL
            r = SERVER_RADIUS
        elif node.locked and nid not in gs.global_unlocks:
            col = LOCKED_COL
        elif node.mine:
            col = MINE_COL
        elif node.decoy:
            col = WARN
        pulse = pygame.time.get_ticks() / 300
        draw_node(screen, x, y, col, pulse)
        pygame.draw.circle(screen, PANEL_ALT, (x, y), r + 1, 1)
        label = small_font.render(str(nid), True, PANEL_ALT)
        label_rect = pygame.Rect(x - 12, y - r - 26, 24, 18)
        draw_panel(
            screen,
            label_rect,
            fill=mix_color(CARD, col, 0.18 if hovered_node == nid or nid == human.current else 0.08),
            border=mix_color(BORDER, col, 0.45),
            radius=9,
        )
        screen.blit(label, (label_rect.centerx - label.get_width() // 2, label_rect.y + 1))

    draw_panel(screen, legend_rect, fill=PANEL_ALT, border=BORDER, radius=20)
    draw_text(screen, "Legend", (legend_rect.x + 16, legend_rect.y + 12), font, ACCENT, shadow=False)
    legend_items = [
        ("Server", SERVER_COL),
        ("Locked", LOCKED_COL),
        ("Mine", MINE_COL),
        ("Decoy", WARN),
    ]
    lx = legend_rect.x + 18
    ly = legend_rect.y + 52
    for label, color in legend_items:
        pygame.draw.circle(screen, color, (lx + 8, ly + 8), 7)
        draw_text(screen, label, (lx + 24, ly - 2), small_font, FG, shadow=False)
        lx += 68

    draw_panel(screen, mission_rect, fill=PANEL_ALT, border=BORDER, radius=24)
    draw_text(screen, "Mission Control", (mission_rect.x + 18, mission_rect.y + 16), title_font, ACCENT, shadow=False)

    overview_rect = pygame.Rect(mission_rect.x + 14, mission_rect.y + 60, mission_rect.w - 28, 154)
    draw_panel(screen, overview_rect, fill=PANEL, border=BORDER, radius=18)
    last_event = gs.log[-1] if gs.log else "Quiet network. Establish sensor coverage."
    overview_items = [
        ("Objective", f"Breach server node {gs.server_id} before your rival does."),
        ("Recommended opener", "mission  >  status  >  sweep  >  hint"),
        ("Known territory", f"{len(disc)} of {len(gs.nodes)} nodes visible"),
        ("Last event", last_event),
    ]
    oy = overview_rect.y + 14
    for label, value in overview_items:
        draw_text(screen, label, (overview_rect.x + 14, oy), small_font, WARN if label == "Objective" else ACCENT, shadow=False)
        oy += small_font.get_height() + 2
        for wrapped_line in wrap_lines(value, small_font, overview_rect.w - 28):
            draw_text(screen, wrapped_line, (overview_rect.x + 14, oy), small_font, FG if label == "Objective" else MUTED, shadow=False)
            oy += small_font.get_height() + 3
        oy += 6

    deck_rect = pygame.Rect(mission_rect.x + 14, overview_rect.bottom + 14, mission_rect.w - 28, mission_rect.bottom - overview_rect.bottom - 28)
    draw_panel(screen, deck_rect, fill=PANEL, border=BORDER, radius=20)
    draw_text(screen, "Command Deck", (deck_rect.x + 14, deck_rect.y + 12), font, WARN, shadow=False)
    scroll_area_h = deck_rect.h - 48
    y = deck_rect.y + 42 - booklet_scroll
    content_h = 0
    desc_x = deck_rect.x + 122
    desc_w = deck_rect.w - 138
    for line in CORE_BOOKLET_TEXT:
        parts = line.split(" - ", 1)
        cmd_text = parts[0]
        desc_text = parts[1] if len(parts) > 1 else ""
        desc_lines = wrap_lines(desc_text, small_font, max(80, desc_w))
        block_h = max(28, max(1, len(desc_lines)) * (small_font.get_height() + 3) + 10)
        row_rect = pygame.Rect(deck_rect.x + 10, y - 4, deck_rect.w - 24, block_h)
        if deck_rect.y + 34 <= y <= deck_rect.bottom - 16:
            draw_panel(screen, row_rect, fill=mix_color(CARD, ACCENT_SOFT, 0.16), border=mix_color(BORDER, ACCENT, 0.22), radius=14)
            draw_text(screen, cmd_text, (deck_rect.x + 18, y + 4), small_font, ACCENT, shadow=False)
            dy = y + 4
            for desc_line in desc_lines or [""]:
                draw_text(screen, desc_line, (desc_x, dy), small_font, FG, shadow=False)
                dy += small_font.get_height() + 3
        y += block_h + 8
        content_h += block_h + 8
    if content_h > scroll_area_h:
        max_scroll = max(0, content_h - scroll_area_h)
        booklet_scroll = max(0, min(booklet_scroll, max_scroll))
        bar_h = max(30, int(scroll_area_h * (scroll_area_h / content_h)))
        bar_y = deck_rect.y + 42 + int((booklet_scroll / max(1, content_h)) * scroll_area_h)
        pygame.draw.rect(screen, BORDER, (deck_rect.right - 10, bar_y, 4, bar_h), border_radius=999)

    draw_panel(screen, term_rect, fill=PANEL, border=BORDER, radius=24)
    draw_text(screen, "Command Terminal", (term_rect.x + 18, term_rect.y + 16), title_font, ACCENT, shadow=False)
    draw_text(
        screen,
        "Use mission, hint, probe, sweep, inventory, and stabilize. Press F2 for network settings.",
        (term_rect.x + 18, term_rect.y + 56),
        small_font,
        MUTED,
        shadow=False,
    )

    log_margin = 8
    input_h = term_font.get_height() + 18
    log_area = pygame.Rect(
        term_rect.x + log_margin + 10,
        term_rect.y + 90,
        term_rect.w - 2 * log_margin - 20,
        term_rect.h - 90 - input_h - 20,
    )
    input_rect = pygame.Rect(
        term_rect.x + log_margin,
        term_rect.bottom - input_h - 10,
        term_rect.w - 2 * log_margin,
        input_h,
    )

    wrapped = []
    for line in term.lines:
        wrapped += wrap_lines(line, term_font, log_area.w)
    max_lines = log_area.h // (term_font.get_height() + 4)
    start_index = max(0, len(wrapped) - max_lines - term.scroll_offset)
    view = wrapped[start_index:start_index + max_lines]
    y = log_area.y
    for line in view:
        draw_text(screen, line, (log_area.x, y), term_font, FG, shadow=False)
        y += term_font.get_height() + 4

    draw_panel(screen, input_rect, fill=INPUT_BG, border=BORDER, radius=16)
    cursor = "_" if term.cursor_visible else " "
    disp = term.input + cursor if term.input else ("type a command ..." if is_online else "press F2 to connect, then type a command ...")
    draw_text(
        screen,
        disp,
        (input_rect.x + 12, input_rect.y + 8),
        term_font,
        FG if term.input else MUTED,
        shadow=False,
    )

    if hovered_node is not None and hovered_node in disc:
        hovered = gs.nodes[hovered_node]
        tooltip_lines = [
            f"Links {', '.join(str(n) for n in sorted(hovered.neighbors)[:6]) or 'none'}",
        ]
        flags = []
        if hovered.server:
            flags.append("server")
        if hovered.locked and hovered_node not in gs.global_unlocks:
            flags.append("locked")
        if hovered.mine:
            flags.append("mine risk")
        if hovered.decoy:
            flags.append("decoy")
        if flags:
            tooltip_lines.insert(0, " / ".join(flags))
        if hovered_node == human.current:
            tooltip_lines.append("Click to queue probe command")
        elif hovered_node in gs.nodes[human.current].neighbors:
            tooltip_lines.append("Left click queues move command")
        else:
            tooltip_lines.append("Left click queues probe command")
        draw_hover_tooltip(
            screen,
            font,
            small_font,
            mouse_pos,
            f"Node {hovered_node}",
            tooltip_lines,
            ACCENT,
        )

    if human_count < 2 and not gs.winner:
        wait_rect = pygame.Rect(MAP_W // 2 - 158, 18, 316, 40)
        draw_panel(screen, wait_rect, fill=mix_color(CARD, WARN, 0.12), border=WARN, radius=20)
        wait_msg = small_font.render("Waiting for second operator to join this room", True, FG)
        screen.blit(wait_msg, (wait_rect.centerx - wait_msg.get_width() // 2, wait_rect.centery - wait_msg.get_height() // 2))

    if gs.winner:
        banner = f"{gs.winner} has hacked the server! Press ESC to quit."
        bimg = title_font.render(banner, True, DANGER)
        screen.blit(bimg, (MAP_W // 2 - bimg.get_width() // 2, 12))

# --------------------------- Entry point ------------------------------

if __name__ == "__main__":
    main()
