// Cyber Hax v5 Game Logic
// Adapted for React/Vite/TypeScript

export const COMMAND_CARDS = [
  { command: "mission", description: "See your objective and best next step.", mode: "send" },
  { command: "status", description: "Check current node, effects, and route distance.", mode: "send" },
  { command: "sweep", description: "Reveal a wider section of the map.", mode: "send" },
  { command: "hint", description: "Get a fast route recommendation.", mode: "send" },
  { command: "inventory", description: "Review collected keys and utility counts.", mode: "send" },
  { command: "reveal", description: "Expose the rival for a short window.", mode: "send" },
  { command: "stabilize", description: "Clear stun and raise a shield.", mode: "send" },
  { command: "log", description: "Review recent public events.", mode: "send" },
  { command: "probe <id>", description: "Queue node intel on a specific target.", mode: "queue" },
  { command: "move <id>", description: "Queue a move to an adjacent unlocked node.", mode: "queue" },
  { command: "unlock <id> auto", description: "Queue auto-unlock when you hold the key.", mode: "queue" },
  { command: "rematch", description: "Vote for another round after the duel ends.", mode: "send" },
];

const SVG_NS = "http://www.w3.org/2000/svg";
const PROFILE_STORAGE_KEY = "cyberHaxProfile";
const SERVER_STORAGE_KEY = "cyberHaxServerBase";
const MATCHMAKING_STORAGE_KEY = "cyberHaxClientId";
const DEPLOYMENT_FALLBACK_SERVER_BASE = "wss://cyber-hax-server.onrender.com";
const HOSTED_BACKEND_HOST = "cyber-hax-server.onrender.com";
const MATCHMAKING_HEARTBEAT_MS = 15000;

export interface GameState {
  ws: WebSocket | null;
  matchmakingWs: WebSocket | null;
  connectionStatus: string;
  matchmakingStatus: string;
  reconnectAttempts: number;
  reconnectTimer: any;
  matchmakingHeartbeatTimer: any;
  serverBase: string;
  sessionName: string;
  playerName: string;
  assignedPlayer: string;
  clientId: string;
  matchmakingMessage: string;
  matchmakingMeta: string;
  gameState: any;
  room: any;
  logs: any[];
  chatMessages: any[];
  hoveredNode: any;
  selectedNode: any;
  signalDots: any[];
  toasts: any[];
  resultKey: string;
  serverNowBase: number;
  clientNowBase: number;
  profile: any;
  fxContext: AudioContext | null;
}

export function initGameState(): GameState {
  return {
    ws: null,
    matchmakingWs: null,
    connectionStatus: "idle",
    matchmakingStatus: "idle",
    reconnectAttempts: 0,
    reconnectTimer: null,
    matchmakingHeartbeatTimer: null,
    serverBase: "",
    sessionName: "",
    playerName: "",
    assignedPlayer: "",
    clientId: loadClientId(),
    matchmakingMessage: "We will create a fresh session and move both players into the same live game as soon as a match is found.",
    matchmakingMeta: "Queue empty. Press find match to search worldwide.",
    gameState: null,
    room: null,
    logs: [
      { text: "Cyber Hax web client ready.", kind: "normal" },
      { text: "Connecting to local uplink...", kind: "normal" },
    ],
    chatMessages: [],
    hoveredNode: null,
    selectedNode: null,
    signalDots: [],
    toasts: [],
    resultKey: "",
    serverNowBase: 0,
    clientNowBase: 0,
    profile: loadProfile(),
    fxContext: null,
  };
}

function loadProfile() {
  try {
    return JSON.parse(localStorage.getItem(PROFILE_STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function loadClientId() {
  try {
    let clientId = localStorage.getItem(MATCHMAKING_STORAGE_KEY) || "";
    if (!clientId) {
      clientId = window.crypto?.randomUUID?.() || `client-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem(MATCHMAKING_STORAGE_KEY, clientId);
    }
    return clientId;
  } catch {
    return `client-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }
}

export function normalizeServerBase(rawValue: string) {
  let value = (rawValue || "").trim();
  if (!value) {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    return `${protocol}://${window.location.host}`;
  }
  if (value.startsWith("http://")) value = `ws://${value.slice(7)}`;
  else if (value.startsWith("https://")) value = `wss://${value.slice(8)}`;
  else if (!/^[a-z]+:\/\//i.test(value)) value = `${window.location.protocol === "https:" ? "wss" : "ws"}://${value}`;
  value = value.replace(/\/+$/, "");
  return value;
}

export function randomCallsign() {
  return `Operator-${Math.floor(100 + Math.random() * 900)}`;
}

// Helper functions for the game logic (simplified for React integration)
export const utils = {
  escapeHtml: (text: string) => {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  },
  formatChatTimestamp: (timestamp: number) => {
    if (!timestamp) return "";
    try {
      return new Date(timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  },
  estimatedServerNow: (state: GameState) => {
    if (!state.serverNowBase) return 0;
    return state.serverNowBase + (performance.now() / 1000 - state.clientNowBase);
  },
  timeLeft: (state: GameState, untilValue: number) => {
    return Math.max(0, (untilValue || 0) - utils.estimatedServerNow(state));
  }
};

export function inferLogKind(text: string): string {
  if (text.startsWith(">")) return "command";
  if (/breached|hacked the server|you win|rematch accepted/i.test(text)) return "winner";
  if (/connected|collected|unlocked|shield|reconnected|room restarted/i.test(text)) return "success";
  if (/waiting|paused|offline|full|vote recorded/i.test(text)) return "warning";
  if (/incorrect|unknown|cannot|not connected|unable|error|locked|malformed/i.test(text)) return "error";
  return "normal";
}

export function bfsDistance(nodes: any, start: number | string, goal: number | string): number | null {
  const s = String(start);
  const g = String(goal);
  if (!nodes || !nodes[s] || !nodes[g]) return null;
  const queue: [string, number][] = [[s, 0]];
  const visited = new Set([s]);
  while (queue.length) {
    const [nodeId, depth] = queue.shift()!;
    if (nodeId === g) return depth;
    for (const neighbor of nodes[nodeId].neighbors || []) {
      const nStr = String(neighbor);
      if (!visited.has(nStr) && nodes[nStr]) {
        visited.add(nStr);
        queue.push([nStr, depth + 1]);
      }
    }
  }
  return null;
}

export function nodeFlags(nodeId: string, gameState: any) {
  if (!gameState?.nodes?.[nodeId]) return [];
  const node = gameState.nodes[nodeId];
  const unlocks = gameState.global_unlocks || [];
  const flags: { label: string; className: string }[] = [];
  if (node.server) flags.push({ label: "Server", className: "server" });
  if (node.locked && !unlocks.includes(Number(nodeId))) flags.push({ label: "Locked", className: "locked" });
  if (node.mine) flags.push({ label: "Mine risk", className: "mine" });
  if (node.decoy) flags.push({ label: "Decoy", className: "decoy" });
  return flags;
}

export function viewerStateLabel(viewer: any, room: any, gameState: any, state: GameState) {
  if (!viewer) return "Standby";
  if (room?.status === "waiting") return "Waiting for opponent";
  if (room?.status === "reconnecting") return "Paused for reconnect";
  if (gameState?.winner) return gameState.winner === viewer.name ? "Victory" : "Defeat";
  if (utils.timeLeft(state, viewer.stunned_until) > 0) return `Stunned ${utils.timeLeft(state, viewer.stunned_until).toFixed(1)}s`;
  if (utils.timeLeft(state, viewer.shield_until) > 0) return `Shielded ${utils.timeLeft(state, viewer.shield_until).toFixed(1)}s`;
  return "Ready";
}

export function nextHint(viewer: any, room: any, gameState: any, selectedNode: string | null) {
  if (!room) return "Connect to a room to receive a live objective.";
  if (room.status === "waiting") return "Share the room link so a second operator can join.";
  if (room.status === "reconnecting") return "Hold position. The duel resumes once both operators are back.";
  if (gameState?.winner) return "Use rematch to keep the room score or restart to reset the room.";
  if (viewer?.stunned_until && viewer.stunned_until > 0) return "Use stabilize or wait out the stun before pushing forward.";
  if (selectedNode != null) {
    return `Selected node ${selectedNode}. Use the node actions or terminal send button to execute the play.`;
  }
  return "Tap a node for intel, tap it again to queue the suggested action, or use mission / hint for quick guidance.";
}
