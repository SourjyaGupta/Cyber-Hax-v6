const COMMAND_CARDS = [
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
const DEPLOYMENT_FALLBACK_SERVER_BASE = "ws://127.0.0.1:8000";

const els = {
  joinSheet: document.getElementById("joinSheet"),
  joinForm: document.getElementById("joinForm"),
  createRoomButton: document.getElementById("createRoomButton"),
  playerInput: document.getElementById("playerInput"),
  sessionInput: document.getElementById("sessionInput"),
  serverInput: document.getElementById("serverInput"),
  joinStatus: document.getElementById("joinStatus"),
  resumeButton: document.getElementById("resumeButton"),
  landingInviteHint: document.getElementById("landingInviteHint"),
  helpButton: document.getElementById("helpButton"),
  inviteButton: document.getElementById("inviteButton"),
  sidebarInviteButton: document.getElementById("sidebarInviteButton"),
  sidebarHelpButton: document.getElementById("sidebarHelpButton"),
  settingsToggle: document.getElementById("settingsToggle"),
  musicToggle: document.getElementById("musicToggle"),
  connectionPill: document.getElementById("connectionPill"),
  sessionPill: document.getElementById("sessionPill"),
  networkSvg: document.getElementById("networkSvg"),
  boardStage: document.getElementById("boardStage"),
  boardTooltip: document.getElementById("boardTooltip"),
  waitingBanner: document.getElementById("waitingBanner"),
  reconnectBanner: document.getElementById("reconnectBanner"),
  winnerBanner: document.getElementById("winnerBanner"),
  toastStack: document.getElementById("toastStack"),
  roomCode: document.getElementById("roomCode"),
  roomNotice: document.getElementById("roomNotice"),
  scoreboardList: document.getElementById("scoreboardList"),
  copyRoomLinkButton: document.getElementById("copyRoomLinkButton"),
  metricPlayer: document.getElementById("metricPlayer"),
  metricMode: document.getElementById("metricMode"),
  metricCurrent: document.getElementById("metricCurrent"),
  metricServer: document.getElementById("metricServer"),
  metricDistance: document.getElementById("metricDistance"),
  metricStatus: document.getElementById("metricStatus"),
  metricOperators: document.getElementById("metricOperators"),
  metricRank: document.getElementById("metricRank"),
  metricUtilities: document.getElementById("metricUtilities"),
  metricNext: document.getElementById("metricNext"),
  selectedNodeCard: document.getElementById("selectedNodeCard"),
  actionHint: document.getElementById("actionHint"),
  matchLabel: document.getElementById("matchLabel"),
  modeLabel: document.getElementById("modeLabel"),
  terminalModePill: document.getElementById("terminalModePill"),
  logOutput: document.getElementById("logOutput"),
  commandDeck: document.getElementById("commandDeck"),
  chatOutput: document.getElementById("chatOutput"),
  chatForm: document.getElementById("chatForm"),
  chatInput: document.getElementById("chatInput"),
  terminalForm: document.getElementById("terminalForm"),
  commandInput: document.getElementById("commandInput"),
  helpModal: document.getElementById("helpModal"),
  inviteModal: document.getElementById("inviteModal"),
  summaryModal: document.getElementById("summaryModal"),
  inviteLinkInput: document.getElementById("inviteLinkInput"),
  inviteMessage: document.getElementById("inviteMessage"),
  inviteStatus: document.getElementById("inviteStatus"),
  copyInviteButton: document.getElementById("copyInviteButton"),
  copyChallengeButton: document.getElementById("copyChallengeButton"),
  whatsAppShareButton: document.getElementById("whatsAppShareButton"),
  summaryHeadline: document.getElementById("summaryHeadline"),
  summaryDetail: document.getElementById("summaryDetail"),
  summaryWinner: document.getElementById("summaryWinner"),
  summaryRoom: document.getElementById("summaryRoom"),
  summaryMatch: document.getElementById("summaryMatch"),
  summaryDuration: document.getElementById("summaryDuration"),
  rematchButton: document.getElementById("rematchButton"),
  restartButton: document.getElementById("restartButton"),
  bgMusic: document.getElementById("bgMusic"),
};

const state = {
  ws: null,
  connectionStatus: "idle",
  reconnectAttempts: 0,
  reconnectTimer: null,
  serverBase: "",
  sessionName: "",
  playerName: "",
  assignedPlayer: "",
  gameState: null,
  room: null,
  logs: [
    { text: "Cyber Hax web client ready.", kind: "normal" },
    { text: "Create a room or join one from a friend to begin.", kind: "normal" },
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

function loadProfile() {
  try {
    return JSON.parse(localStorage.getItem(PROFILE_STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveProfile() {
  localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(state.profile));
}

function loadStoredServerBase() {
  try {
    return normalizeServerBase(localStorage.getItem(SERVER_STORAGE_KEY) || "");
  } catch {
    return defaultServerBase();
  }
}

function saveServerBase(value) {
  try {
    localStorage.setItem(SERVER_STORAGE_KEY, normalizeServerBase(value));
  } catch {}
}

function playerStats(name) {
  const key = (name || "operator").toLowerCase();
  if (!state.profile[key]) state.profile[key] = { wins: 0, games: 0, streak: 0, bestStreak: 0 };
  return state.profile[key];
}

function rankLabel(stats) {
  if (!stats.games) return "Trace Rookie";
  if (stats.wins >= 10) return "Core Breaker";
  if (stats.wins >= 6) return "Signal Hunter";
  if (stats.wins >= 3) return "Relay Raider";
  return "Probe Runner";
}

function randomCallsign() {
  return `Operator-${Math.floor(100 + Math.random() * 900)}`;
}

function defaultServerBase() {
  // Local build prefers same-origin when served by FastAPI and falls back to localhost for direct testing.
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const host = (window.location.hostname || "").toLowerCase();
  if (!window.location.host || window.location.protocol === "file:") return DEPLOYMENT_FALLBACK_SERVER_BASE;
  if (host === "127.0.0.1" || host === "localhost") return `${protocol}://${window.location.host}`;
  if (host.endsWith(".itch.io") || host.endsWith(".itch.zone") || host.endsWith(".hwcdn.net")) return DEPLOYMENT_FALLBACK_SERVER_BASE;
  return `${protocol}://${window.location.host}`;
}

function normalizeServerBase(rawValue) {
  let value = (rawValue || "").trim();
  if (!value) return defaultServerBase();
  if (value.startsWith("http://")) value = `ws://${value.slice(7)}`;
  else if (value.startsWith("https://")) value = `wss://${value.slice(8)}`;
  else if (!/^[a-z]+:\/\//i.test(value)) value = `${window.location.protocol === "https:" ? "wss" : "ws"}://${value}`;
  value = value.replace(/\/+$/, "");
  const wsIndex = value.indexOf("/ws/");
  return wsIndex >= 0 ? value.slice(0, wsIndex) : value;
}

function apiBaseFromServerBase(serverBase) {
  const value = normalizeServerBase(serverBase);
  if (value.startsWith("wss://")) return `https://${value.slice(6)}`;
  if (value.startsWith("ws://")) return `http://${value.slice(5)}`;
  return value.replace(/\/+$/, "");
}

function safeRoomName(rawValue) {
  return (rawValue || "").trim().replace(/\s+/g, "-").slice(0, 32) || "session1";
}

function estimatedServerNow() {
  if (!state.serverNowBase) return 0;
  return state.serverNowBase + (performance.now() / 1000 - state.clientNowBase);
}

function timeLeft(untilValue) {
  return Math.max(0, (untilValue || 0) - estimatedServerNow());
}

function setSheetOpen(isOpen) {
  els.joinSheet.classList.toggle("is-open", isOpen);
  document.body.classList.toggle("sheet-open", isOpen);
}

function openModal(modal) {
  modal.classList.remove("hidden");
  document.body.classList.add("modal-open");
}

function closeModal(modal) {
  modal.classList.add("hidden");
  const openModals = document.querySelectorAll(".modal:not(.hidden)");
  document.body.classList.toggle("modal-open", openModals.length > 0);
}

function updateJoinStatus(message, tone = "muted") {
  els.joinStatus.textContent = message;
  els.joinStatus.dataset.tone = tone;
}

function updateMusicButton() {
  els.musicToggle.textContent = els.bgMusic.paused ? "Start Music" : "Pause Music";
}

function updateConnectionChrome() {
  const labels = { idle: "Offline", connecting: "Connecting", connected: "Online", reconnecting: "Reconnecting", disconnected: "Disconnected" };
  els.connectionPill.textContent = labels[state.connectionStatus] || "Offline";
  els.connectionPill.classList.toggle("muted", state.connectionStatus !== "connected");
  els.sessionPill.textContent = `Room ${state.sessionName || "------"}`;
  els.resumeButton.disabled = state.connectionStatus !== "connected";
}

function syncUrl() {
  const url = new URL(window.location.href);
  if (state.playerName) url.searchParams.set("player", state.playerName);
  if (state.sessionName) url.searchParams.set("session", state.sessionName);
  if (state.serverBase) url.searchParams.set("server", state.serverBase);
  window.history.replaceState({}, "", url);
}

function inferLogKind(text) {
  if (text.startsWith(">")) return "command";
  if (/breached|hacked the server|you win|rematch accepted/i.test(text)) return "winner";
  if (/connected|collected|unlocked|shield|reconnected|room restarted/i.test(text)) return "success";
  if (/waiting|paused|offline|full|vote recorded/i.test(text)) return "warning";
  if (/incorrect|unknown|cannot|not connected|unable|error|locked|malformed/i.test(text)) return "error";
  return "normal";
}

function pushToast(text, tone = "normal") {
  const id = `${Date.now()}-${Math.random()}`;
  state.toasts.push({ id, text, tone });
  state.toasts = state.toasts.slice(-4);
  renderToasts();
  window.setTimeout(() => {
    state.toasts = state.toasts.filter((toast) => toast.id !== id);
    renderToasts();
  }, 3200);
}

function appendLog(lines, forcedKind = "") {
  for (const line of Array.isArray(lines) ? lines : [lines]) {
    if (!line) continue;
    const kind = forcedKind || inferLogKind(line);
    state.logs.push({ text: line, kind });
    if (["winner", "success", "error", "warning"].includes(kind) && !line.startsWith(">")) pushToast(line, kind);
  }
  state.logs = state.logs.slice(-240);
  renderLogs();
}

function renderLogs() {
  els.logOutput.innerHTML = "";
  for (const entry of state.logs) {
    const line = document.createElement("div");
    line.className = `log-line${entry.kind !== "normal" ? ` ${entry.kind}` : ""}`;
    line.textContent = entry.text;
    els.logOutput.appendChild(line);
  }
  els.logOutput.scrollTop = els.logOutput.scrollHeight;
}

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatChatTimestamp(timestamp) {
  if (!timestamp) return "";
  try {
    return new Date(timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function renderChat() {
  if (!state.chatMessages.length) {
    els.chatOutput.innerHTML = '<div class="chat-empty">Room chat is live. Send the first message.</div>';
    return;
  }

  const viewerName = state.assignedPlayer || state.playerName;
  els.chatOutput.innerHTML = state.chatMessages.map((message) => {
    const mine = message.player_name === viewerName;
    return `
      <div class="chat-line${mine ? " mine" : ""}">
        <div class="chat-meta">
          <span class="chat-author">${escapeHtml(message.player_name || "Operator")}</span>
          <span>${formatChatTimestamp(message.timestamp)}</span>
        </div>
        <div class="chat-text">${escapeHtml(message.text || "")}</div>
      </div>
    `;
  }).join("");
  els.chatOutput.scrollTop = els.chatOutput.scrollHeight;
}

function renderToasts() {
  els.toastStack.innerHTML = state.toasts.map((toast) => `<div class="toast ${toast.tone}">${toast.text}</div>`).join("");
}

async function ensureFxContext() {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return null;
  if (!state.fxContext) state.fxContext = new AudioCtx();
  if (state.fxContext.state === "suspended") {
    try {
      await state.fxContext.resume();
    } catch {
      return null;
    }
  }
  return state.fxContext;
}

function playUiTone(kind = "soft") {
  const ctx = state.fxContext;
  if (!ctx || ctx.state !== "running") return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  const settings = {
    soft: { freq: 420, gain: 0.018, duration: 0.08 },
    success: { freq: 620, gain: 0.028, duration: 0.11 },
    error: { freq: 210, gain: 0.028, duration: 0.12 },
    winner: { freq: 760, gain: 0.035, duration: 0.16 },
  }[kind] || { freq: 420, gain: 0.018, duration: 0.08 };
  osc.type = "triangle";
  osc.frequency.value = settings.freq;
  gain.gain.value = settings.gain;
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + settings.duration);
  osc.stop(ctx.currentTime + settings.duration);
}

async function toggleMusic() {
  await ensureFxContext();
  if (els.bgMusic.paused) {
    els.bgMusic.volume = 0.42;
    try {
      await els.bgMusic.play();
      updateJoinStatus("Music armed. Browser audio starts after a user interaction.", "accent");
      playUiTone("soft");
    } catch {
      updateJoinStatus("The browser blocked music until another click. Try the button again.", "warning");
    }
  } else {
    els.bgMusic.pause();
  }
  updateMusicButton();
}

function buildRoomLink() {
  if (!state.sessionName) return "";
  const url = new URL(window.location.href);
  url.searchParams.set("session", state.sessionName);
  url.searchParams.set("server", state.serverBase || defaultServerBase());
  return url.toString();
}

function buildChallengeText() {
  const roomLink = buildRoomLink();
  if (!roomLink) return "";
  return `Join me in Cyber Hax. Two operators, one live network duel. Room ${state.sessionName}: ${roomLink}`;
}

async function copyText(text, successMessage) {
  if (!text) {
    pushToast("Create or join a room first.", "warning");
    return;
  }
  await ensureFxContext();
  try {
    await navigator.clipboard.writeText(text);
    pushToast(successMessage, "success");
    playUiTone("success");
  } catch {
    pushToast("Clipboard access failed in this browser.", "error");
    playUiTone("error");
  }
}

function refreshInviteFields() {
  const roomLink = buildRoomLink();
  const challengeText = buildChallengeText();
  els.inviteLinkInput.value = roomLink;
  els.inviteMessage.value = challengeText;
  els.inviteStatus.textContent = roomLink ? "Share this link with your opponent. They only need the page and room code." : "Create or join a room first to generate a shareable invite.";
  els.whatsAppShareButton.href = roomLink ? `https://wa.me/?text=${encodeURIComponent(challengeText)}` : "#";
}
function getViewer() {
  if (!state.gameState?.players?.length) return null;
  return state.gameState.players.find((player) => player.name === state.assignedPlayer)
    || state.gameState.players.find((player) => player.name === state.playerName)
    || state.gameState.players.find((player) => player.is_human)
    || state.gameState.players[0]
    || null;
}

function getOpponent(viewer) {
  return state.gameState?.players?.find((player) => player.is_human && player.name !== viewer?.name) || null;
}

function visibleSetForViewer(viewer) {
  return new Set([...(viewer?.discovered || []), ...(viewer?.reveal_nodes || [])]);
}

function bfsDistance(nodes, start, goal) {
  if (!nodes || !nodes[start] || !nodes[goal]) return null;
  const queue = [[start, 0]];
  const visited = new Set([start]);
  while (queue.length) {
    const [nodeId, depth] = queue.shift();
    if (nodeId === goal) return depth;
    for (const neighbor of nodes[nodeId].neighbors || []) {
      if (!visited.has(neighbor) && nodes[neighbor]) {
        visited.add(neighbor);
        queue.push([neighbor, depth + 1]);
      }
    }
  }
  return null;
}

function nodeFlags(nodeId) {
  if (!state.gameState?.nodes?.[nodeId]) return [];
  const node = state.gameState.nodes[nodeId];
  const unlocks = state.gameState.global_unlocks || [];
  const flags = [];
  if (node.server) flags.push({ label: "Server", className: "server" });
  if (node.locked && !unlocks.includes(Number(nodeId))) flags.push({ label: "Locked", className: "locked" });
  if (node.mine) flags.push({ label: "Mine risk", className: "mine" });
  if (node.decoy) flags.push({ label: "Decoy", className: "decoy" });
  return flags;
}

function currentNodeAction(nodeId) {
  const viewer = getViewer();
  if (!viewer || !state.gameState?.nodes?.[nodeId]) return "";
  if (Number(nodeId) === Number(viewer.current)) return `probe ${nodeId}`;
  const currentNode = state.gameState.nodes[viewer.current];
  const node = state.gameState.nodes[nodeId];
  const adjacent = (currentNode.neighbors || []).includes(Number(nodeId));
  const unlocked = !node.locked || (state.gameState.global_unlocks || []).includes(Number(nodeId));
  return adjacent && unlocked ? `move ${nodeId}` : `probe ${nodeId}`;
}

function viewerStateLabel(viewer) {
  if (!viewer) return "Standby";
  if (state.room?.status === "waiting") return "Waiting for opponent";
  if (state.room?.status === "reconnecting") return "Paused for reconnect";
  if (state.gameState?.winner) return state.gameState.winner === viewer.name ? "Victory" : "Defeat";
  if (timeLeft(viewer.stunned_until) > 0) return `Stunned ${timeLeft(viewer.stunned_until).toFixed(1)}s`;
  if (timeLeft(viewer.shield_until) > 0) return `Shielded ${timeLeft(viewer.shield_until).toFixed(1)}s`;
  return "Ready";
}

function nextHint(viewer) {
  if (!state.room) return "Connect to a room to receive a live objective.";
  if (state.room.status === "waiting") return "Share the room link so a second operator can join.";
  if (state.room.status === "reconnecting") return "Hold position. The duel resumes once both operators are back.";
  if (state.gameState?.winner) return "Use rematch to keep the room score or restart to reset the room.";
  if (timeLeft(viewer?.stunned_until) > 0) return "Use stabilize or wait out the stun before pushing forward.";
  if (state.selectedNode != null) return `Queued focus: ${currentNodeAction(state.selectedNode)} from the selected node.`;
  return "Hover nodes for intel, click a node to queue a command, or run mission / hint.";
}

function sendChat(text) {
  const trimmed = (text || "").trim();
  if (!trimmed) return;
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    pushToast("Chat is offline until you reconnect to the room.", "warning");
    playUiTone("error");
    return;
  }
  state.ws.send(JSON.stringify({ type: "chat", text: trimmed.slice(0, 280) }));
  els.chatInput.value = "";
  playUiTone("soft");
}

function sendCommand(command) {
  const trimmed = (command || "").trim();
  if (!trimmed) return;
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    appendLog("[Network] Not connected. Open Room Settings first.");
    playUiTone("error");
    return;
  }
  state.ws.send(JSON.stringify({ type: "command", command: trimmed }));
  appendLog(`> ${trimmed}`, "command");
  els.commandInput.value = "";
  playUiTone("soft");
}

function sendControl(action) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    appendLog("[Network] Not connected. Control action was not sent.");
    playUiTone("error");
    return;
  }
  state.ws.send(JSON.stringify({ type: "control", action }));
  appendLog(`> ${action}`, "command");
}

function queueCommand(command) {
  if (!command) return;
  els.commandInput.value = command;
  els.commandInput.focus();
  playUiTone("soft");
}

function scheduleReconnect() {
  if (!state.playerName || !state.sessionName || state.reconnectAttempts >= 5) return;
  window.clearTimeout(state.reconnectTimer);
  state.reconnectAttempts += 1;
  state.connectionStatus = "reconnecting";
  updateConnectionChrome();
  updateJoinStatus(`Connection dropped. Reconnecting to room ${state.sessionName}...`, "warning");
  state.reconnectTimer = window.setTimeout(() => connectToServer(null, { silent: true, reconnecting: true }), 900 + state.reconnectAttempts * 700);
}

function connectToServer(event, options = {}) {
  if (event) event.preventDefault();
  window.clearTimeout(state.reconnectTimer);
  state.playerName = (els.playerInput.value || "").trim() || randomCallsign();
  state.sessionName = safeRoomName(els.sessionInput.value);
  state.serverBase = normalizeServerBase(els.serverInput.value);
  state.chatMessages = [];
  state.hoveredNode = null;
  state.selectedNode = null;
  els.playerInput.value = state.playerName;
  els.sessionInput.value = state.sessionName;
  els.serverInput.value = state.serverBase;
  saveServerBase(state.serverBase);
  syncUrl();

  if (state.ws) {
    try {
      state.ws.onclose = null;
      state.ws.close();
    } catch {}
  }

  const socket = new WebSocket(`${state.serverBase}/ws/${encodeURIComponent(state.sessionName)}`);
  state.ws = socket;
  state.connectionStatus = options.reconnecting ? "reconnecting" : "connecting";
  updateConnectionChrome();
  if (!options.silent) updateJoinStatus("Dialing the live session server...", "accent");

  socket.onopen = () => {
    if (socket !== state.ws) return;
    socket.send(JSON.stringify({ type: "join", player_name: state.playerName }));
  };

  socket.onmessage = (message) => {
    if (socket !== state.ws) return;
    const payload = JSON.parse(message.data);
    if (payload.type === "welcome") {
      state.connectionStatus = "connected";
      state.assignedPlayer = payload.player_name || state.playerName;
      state.room = payload.room || state.room;
      state.reconnectAttempts = 0;
      updateJoinStatus(`Linked as ${state.assignedPlayer}. Invite a rival or start reading the map.`, "accent");
      updateConnectionChrome();
      setSheetOpen(false);
      refreshInviteFields();
      playUiTone("success");
    } else if (payload.type === "chat_history") {
      state.chatMessages = Array.isArray(payload.messages) ? payload.messages.slice(-80) : [];
      renderChat();
    } else if (payload.type === "chat") {
      if (payload.message) {
        state.chatMessages.push(payload.message);
        state.chatMessages = state.chatMessages.slice(-80);
        renderChat();
        if (payload.message.player_name !== (state.assignedPlayer || state.playerName)) {
          pushToast(`Chat from ${payload.message.player_name}: ${payload.message.text}`, "success");
        }
      }
    } else if (payload.type === "log") {
      appendLog(payload.lines || []);
    } else if (payload.type === "state") {
      state.gameState = payload.state || null;
      state.room = payload.room || state.room;
      state.assignedPlayer = payload.player_name || state.assignedPlayer;
      state.serverNowBase = state.gameState?.server_now || 0;
      state.clientNowBase = performance.now() / 1000;
      syncResultState();
      renderAll();
    } else if (payload.type === "error") {
      updateJoinStatus(payload.message || "Unknown server error.", "danger");
      appendLog(`[Network] ${payload.message || "Unknown server error."}`);
      playUiTone("error");
    }
  };

  socket.onerror = () => {
    if (socket !== state.ws) return;
    updateJoinStatus("Unable to reach the server.", "danger");
  };

  socket.onclose = () => {
    if (socket !== state.ws) return;
    state.connectionStatus = "disconnected";
    updateConnectionChrome();
    updateJoinStatus("Connection closed. Attempting to recover the room link.", "warning");
    renderAll();
    scheduleReconnect();
  };
}

async function createRoomAndConnect() {
  await ensureFxContext();
  updateJoinStatus("Reserving a new duel room...", "accent");
  try {
    const selectedServerBase = normalizeServerBase(els.serverInput.value || state.serverBase || defaultServerBase());
    state.serverBase = selectedServerBase;
    els.serverInput.value = selectedServerBase;
    saveServerBase(selectedServerBase);
    const response = await fetch(`${apiBaseFromServerBase(selectedServerBase)}/api/rooms/new`);
    if (!response.ok) throw new Error(`room-create-${response.status}`);
    const payload = await response.json();
    if (!payload.room_id) throw new Error("room-create-empty");
    els.sessionInput.value = payload.room_id || "";
    state.sessionName = payload.room_id || "";
    refreshInviteFields();
    connectToServer();
  } catch {
    updateJoinStatus("Create Room is unavailable on this server. Enter a room code manually and press Join Room.", "warning");
    els.sessionInput.focus();
    playUiTone("error");
  }
}
function syncResultState() {
  const summary = state.room?.result_summary;
  if (!summary) {
    closeModal(els.summaryModal);
    return;
  }
  els.summaryHeadline.textContent = summary.headline || "Match complete";
  els.summaryDetail.textContent = summary.detail || "The duel has ended.";
  els.summaryWinner.textContent = summary.winner || "-";
  els.summaryRoom.textContent = summary.session_id || state.sessionName || "-";
  els.summaryMatch.textContent = `#${summary.match_number || "-"}`;
  els.summaryDuration.textContent = `${summary.duration_seconds || "-"}s`;

  const resultKey = `${summary.session_id}:${summary.match_number}:${summary.winner}`;
  if (state.resultKey !== resultKey) {
    state.resultKey = resultKey;
    const viewer = state.assignedPlayer || state.playerName;
    if (viewer) {
      const stats = playerStats(viewer);
      stats.games += 1;
      if (summary.winner === viewer) {
        stats.wins += 1;
        stats.streak += 1;
        stats.bestStreak = Math.max(stats.bestStreak, stats.streak);
      } else {
        stats.streak = 0;
      }
      saveProfile();
    }
    pushToast(summary.headline || "Match complete", "winner");
    playUiTone("winner");
  }
  openModal(els.summaryModal);
}

function renderRoomCard() {
  els.roomCode.textContent = state.sessionName || "------";
  els.roomNotice.textContent = state.room?.notice || "Create or join a room to generate a shareable invite.";
  els.matchLabel.textContent = state.room?.match_number ? `#${state.room.match_number}` : "#-";
  els.modeLabel.textContent = state.room?.status ? state.room.status.toUpperCase() : "OFFLINE";
  refreshInviteFields();

  const scoreboard = state.room?.scoreboard || [];
  els.scoreboardList.innerHTML = scoreboard.length
    ? scoreboard.map((entry) => `
        <div class="score-row">
          <div>
            <div class="score-name">
              <span class="presence-dot${entry.connected ? " live" : ""}"></span>
              <span>${entry.name}</span>
            </div>
            <div class="score-sub">Streak ${entry.streak} • Best ${entry.best_streak}</div>
          </div>
          <div class="score-wins">
            <strong>${entry.wins}</strong>
            <span>wins</span>
          </div>
        </div>
      `).join("")
    : `<div class="score-row"><div class="score-main">Room score appears here after players join.</div></div>`;

  const status = state.room?.status;
  els.waitingBanner.classList.toggle("hidden", status !== "waiting");
  els.waitingBanner.textContent = "Room armed. Share the invite link and wait for the second operator.";
  els.reconnectBanner.classList.toggle("hidden", status !== "reconnecting");
  els.reconnectBanner.textContent = "Opponent disconnected. The duel is paused until they reconnect.";
  els.winnerBanner.classList.toggle("hidden", !state.gameState?.winner);
  els.winnerBanner.textContent = state.gameState?.winner ? `${state.gameState.winner} breached the server core` : "";
}

function renderHud() {
  const viewer = getViewer();
  const stats = playerStats(state.assignedPlayer || state.playerName || "");
  els.metricRank.textContent = rankLabel(stats);
  els.metricMode.textContent = state.room?.status || "offline";
  els.terminalModePill.textContent = viewerStateLabel(viewer);
  els.actionHint.textContent = nextHint(viewer);

  if (!state.gameState || !viewer) {
    els.metricPlayer.textContent = state.assignedPlayer || state.playerName || "Standby";
    els.metricCurrent.textContent = "-";
    els.metricServer.textContent = "-";
    els.metricDistance.textContent = "-";
    els.metricStatus.textContent = state.connectionStatus === "connected" ? "Linked" : "Waiting";
    els.metricOperators.textContent = "0 / 2";
    els.metricUtilities.textContent = "Sweeps -, Patch -, Traps -, Decoys -";
    els.metricNext.textContent = nextHint(viewer);
    return;
  }

  const visible = visibleSetForViewer(viewer);
  const connected = state.room?.connected_players?.length || 0;
  els.metricPlayer.textContent = viewer.name;
  els.metricCurrent.textContent = `${viewer.current}`;
  els.metricServer.textContent = `${state.gameState.server_id}`;
  els.metricDistance.textContent = `${bfsDistance(state.gameState.nodes, viewer.current, state.gameState.server_id) ?? "-"}`;
  els.metricStatus.textContent = viewerStateLabel(viewer);
  els.metricOperators.textContent = `${connected} / ${state.room?.player_capacity || 2}`;
  els.metricUtilities.textContent = `Sweeps ${viewer.sweeps_left}, Patch ${viewer.patch_kits}, Traps ${viewer.traps_left}, Decoys ${viewer.decoys_left}, Visible ${visible.size}/${Object.keys(state.gameState.nodes).length}`;
  els.metricNext.textContent = nextHint(viewer);
}

function renderSelectedNodeCard() {
  const viewer = getViewer();
  const nodeId = state.hoveredNode ?? state.selectedNode;
  if (!state.gameState?.nodes?.[nodeId]) {
    els.selectedNodeCard.textContent = "Select or hover a node to inspect its links, risks, and contextual actions.";
    return;
  }
  const node = state.gameState.nodes[nodeId];
  const flags = nodeFlags(nodeId);
  const links = (node.neighbors || []).slice().sort((a, b) => a - b).join(", ") || "none";
  const action = currentNodeAction(nodeId);
  const autoUnlock = viewer?.collected_pwds?.[String(nodeId)] ? `unlock ${nodeId} auto` : "";
  els.selectedNodeCard.innerHTML = `
    <h4>Node ${nodeId}</h4>
    <div class="tag-row">
      ${flags.length ? flags.map((flag) => `<span class="tag ${flag.className}">${flag.label}</span>`).join("") : '<span class="tag">Stable</span>'}
    </div>
    <p>Links: ${links}</p>
    <p>Recommended action: ${action}</p>
    <div class="action-row">
      <button type="button" data-queue="${action}">Queue ${action}</button>
      <button type="button" data-queue="path ${nodeId}">Queue path</button>
      <button type="button" data-queue="probe ${nodeId}">Queue probe</button>
      ${autoUnlock ? `<button type="button" data-queue="${autoUnlock}">Queue unlock</button>` : ""}
    </div>
  `;
  els.selectedNodeCard.querySelectorAll("[data-queue]").forEach((button) => {
    button.addEventListener("click", () => queueCommand(button.dataset.queue));
  });
}

function createSvg(tagName, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tagName);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  return node;
}

function renderTooltip(event) {
  const nodeId = state.hoveredNode;
  if (!state.gameState?.nodes?.[nodeId]) {
    els.boardTooltip.classList.add("hidden");
    return;
  }
  const node = state.gameState.nodes[nodeId];
  const action = currentNodeAction(nodeId);
  const flags = nodeFlags(nodeId).map((flag) => flag.label).join(" / ") || "Stable";
  const links = (node.neighbors || []).slice().sort((a, b) => a - b).join(", ") || "none";
  els.boardTooltip.innerHTML = `<strong>Node ${nodeId}</strong><br />${flags}<br />Links: ${links}<br />Suggested action: ${action}`;
  const rect = els.boardStage.getBoundingClientRect();
  const x = event ? event.clientX - rect.left + 18 : 24;
  const y = event ? event.clientY - rect.top + 18 : 24;
  els.boardTooltip.style.left = `${Math.min(x, rect.width - 280)}px`;
  els.boardTooltip.style.top = `${Math.min(y, rect.height - 140)}px`;
  els.boardTooltip.classList.remove("hidden");
}
function renderMap() {
  const svg = els.networkSvg;
  svg.innerHTML = "";
  state.signalDots = [];
  const viewer = getViewer();
  if (!viewer || !state.gameState) return;

  const visible = visibleSetForViewer(viewer);
  const opponent = getOpponent(viewer);
  const edgeLayer = createSvg("g");
  const signalLayer = createSvg("g");
  const nodeLayer = createSvg("g");

  for (const [a, b] of state.gameState.edges || []) {
    if (!visible.has(a) || !visible.has(b)) continue;
    const nodeA = state.gameState.nodes[a];
    const nodeB = state.gameState.nodes[b];
    edgeLayer.appendChild(createSvg("line", {
      x1: nodeA.pos[0], y1: nodeA.pos[1], x2: nodeB.pos[0], y2: nodeB.pos[1],
      class: `edge-line${state.hoveredNode === a || state.hoveredNode === b || viewer.current === a || viewer.current === b ? " active" : ""}`,
    }));
    const signalDot = createSvg("circle", { r: 4, class: "signal-dot" });
    signalLayer.appendChild(signalDot);
    state.signalDots.push({ el: signalDot, from: nodeA.pos, to: nodeB.pos, offset: ((a + b) * 0.173) % 1, speed: 0.17 + (((a * 7 + b * 11) % 10) / 100) });
  }

  [...visible].sort((a, b) => a - b).forEach((nodeId) => {
    const node = state.gameState.nodes[nodeId];
    const group = createSvg("g", { class: "node-group" });
    const isCurrent = Number(nodeId) === Number(viewer.current);
    const isOpponent = opponent && Number(nodeId) === Number(opponent.current);
    const isHovered = Number(nodeId) === Number(state.hoveredNode);
    const isSelected = Number(nodeId) === Number(state.selectedNode);
    const unlocked = (state.gameState.global_unlocks || []).includes(Number(nodeId));

    let color = "#eef6ff";
    if (node.server) color = "var(--server)";
    else if (node.locked && !unlocked) color = "var(--locked)";
    else if (node.mine) color = "var(--mine)";
    else if (node.decoy) color = "var(--warn)";

    if (isCurrent || isHovered || isSelected) group.appendChild(createSvg("circle", { cx: node.pos[0], cy: node.pos[1], r: isCurrent ? 31 : 27, class: "node-halo" }));
    if (isOpponent) group.appendChild(createSvg("circle", { cx: node.pos[0], cy: node.pos[1], r: 29, class: "node-halo rival" }));

    group.appendChild(createSvg("circle", { cx: node.pos[0], cy: node.pos[1], r: node.server ? 17 : 14, class: "node-ring" }));
    group.appendChild(createSvg("circle", { cx: node.pos[0], cy: node.pos[1], r: node.server ? 12 : 10, fill: color, class: "node-core" }));

    const labelWidth = String(nodeId).length > 1 ? 28 : 22;
    group.appendChild(createSvg("rect", { x: node.pos[0] - labelWidth / 2, y: node.pos[1] - 36, width: labelWidth, height: 18, rx: 8, class: "node-label-bg" }));
    const label = createSvg("text", { x: node.pos[0], y: node.pos[1] - 23, "text-anchor": "middle", class: "node-label" });
    label.textContent = nodeId;
    group.appendChild(label);

    if (isCurrent || isOpponent) {
      const initials = (isCurrent ? viewer.name : opponent.name).slice(0, 2).toUpperCase();
      group.appendChild(createSvg("rect", { x: node.pos[0] + 11, y: node.pos[1] - 22, width: 22, height: 16, rx: 8, class: `occupant-badge ${isCurrent ? "viewer" : "rival"}` }));
      const badge = createSvg("text", { x: node.pos[0] + 22, y: node.pos[1] - 10, "text-anchor": "middle", class: "occupant-text" });
      badge.textContent = initials;
      group.appendChild(badge);
    }

    group.addEventListener("mouseenter", () => {
      state.hoveredNode = nodeId;
      renderSelectedNodeCard();
      renderMap();
      renderTooltip();
    });
    group.addEventListener("mousemove", (event) => {
      state.hoveredNode = nodeId;
      renderTooltip(event);
    });
    group.addEventListener("mouseleave", () => {
      state.hoveredNode = null;
      els.boardTooltip.classList.add("hidden");
      renderSelectedNodeCard();
      renderMap();
    });
    group.addEventListener("click", async () => {
      await ensureFxContext();
      state.selectedNode = nodeId;
      queueCommand(currentNodeAction(nodeId));
      renderSelectedNodeCard();
      renderMap();
    });

    nodeLayer.appendChild(group);
  });

  svg.appendChild(edgeLayer);
  svg.appendChild(signalLayer);
  svg.appendChild(nodeLayer);
}

function renderCommandDeck() {
  els.commandDeck.innerHTML = COMMAND_CARDS.map((item) => `
    <button class="command-card" type="button" data-mode="${item.mode}" data-command="${item.command}">
      <strong>${item.command}</strong>
      <span>${item.description}</span>
    </button>
  `).join("");
  els.commandDeck.querySelectorAll(".command-card").forEach((button) => {
    button.addEventListener("click", async () => {
      await ensureFxContext();
      if (button.dataset.mode === "send") sendCommand(button.dataset.command);
      else queueCommand(button.dataset.command);
    });
  });
}

function renderAll() {
  updateConnectionChrome();
  renderRoomCard();
  renderHud();
  renderSelectedNodeCard();
  renderChat();
  renderMap();
}

function animateSignals(timestamp) {
  state.signalDots.forEach((signal) => {
    const progress = (timestamp * 0.00008 * signal.speed + signal.offset) % 1;
    const cx = signal.from[0] + (signal.to[0] - signal.from[0]) * progress;
    const cy = signal.from[1] + (signal.to[1] - signal.from[1]) * progress;
    signal.el.setAttribute("cx", cx.toFixed(2));
    signal.el.setAttribute("cy", cy.toFixed(2));
  });
  window.requestAnimationFrame(animateSignals);
}

function bootstrap() {
  const params = new URLSearchParams(window.location.search);
  state.playerName = params.get("player") || randomCallsign();
  state.sessionName = params.get("session") || "";
  state.serverBase = normalizeServerBase(params.get("server") || loadStoredServerBase() || defaultServerBase());
  els.playerInput.value = state.playerName;
  els.sessionInput.value = state.sessionName;
  els.serverInput.value = state.serverBase;
  els.landingInviteHint.textContent = state.sessionName ? `Invite detected for room ${state.sessionName}. Add a callsign and join the duel.` : "Create a room to challenge a friend or paste a room code to join instantly.";

  renderCommandDeck();
  renderLogs();
  renderChat();
  renderToasts();
  renderAll();
  refreshInviteFields();
  updateJoinStatus("Set a callsign, create or enter a room, and connect to the live session server.");

  els.joinForm.addEventListener("submit", connectToServer);
  els.createRoomButton.addEventListener("click", createRoomAndConnect);
  els.resumeButton.addEventListener("click", () => state.connectionStatus === "connected" && setSheetOpen(false));
  els.settingsToggle.addEventListener("click", () => setSheetOpen(true));
  els.helpButton.addEventListener("click", () => openModal(els.helpModal));
  els.sidebarHelpButton.addEventListener("click", () => openModal(els.helpModal));
  els.inviteButton.addEventListener("click", () => { refreshInviteFields(); openModal(els.inviteModal); });
  els.sidebarInviteButton.addEventListener("click", () => { refreshInviteFields(); openModal(els.inviteModal); });
  els.copyRoomLinkButton.addEventListener("click", () => copyText(buildRoomLink(), "Room link copied."));
  els.copyInviteButton.addEventListener("click", () => copyText(buildRoomLink(), "Invite link copied."));
  els.copyChallengeButton.addEventListener("click", () => copyText(buildChallengeText(), "Challenge message copied."));
  els.rematchButton.addEventListener("click", () => sendControl("rematch"));
  els.restartButton.addEventListener("click", () => sendControl("restart"));
  els.terminalForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendCommand(els.commandInput.value);
  });
  els.chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendChat(els.chatInput.value);
  });
  els.musicToggle.addEventListener("click", toggleMusic);
  els.bgMusic.volume = 0.42;
  els.bgMusic.addEventListener("play", updateMusicButton);
  els.bgMusic.addEventListener("pause", updateMusicButton);

  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", () => closeModal(document.getElementById(button.dataset.closeModal)));
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeModal(els.helpModal);
      closeModal(els.inviteModal);
      closeModal(els.summaryModal);
      if (state.connectionStatus === "connected") setSheetOpen(false);
    }
    if (event.key === "F2") {
      event.preventDefault();
      setSheetOpen(true);
    }
  });

  if (params.get("player") && params.get("session")) connectToServer(null, { silent: true });

  updateMusicButton();
  window.setInterval(() => {
    if (state.gameState) renderHud();
  }, 250);
  window.requestAnimationFrame(animateSignals);
}

bootstrap();
