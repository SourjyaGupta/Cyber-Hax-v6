import express from "express";
import { createServer } from "http";
import { WebSocketServer, WebSocket } from "ws";
import { createServer as createViteServer } from "vite";
import path from "path";

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ noServer: true });
const matchmakingWss = new WebSocketServer({ noServer: true });

server.on('upgrade', (request, socket, head) => {
  const pathname = new URL(request.url!, `http://${request.headers.host}`).pathname;

  if (pathname.startsWith('/ws/')) {
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit('connection', ws, request);
    });
  } else if (pathname === '/ws-matchmaking') {
    matchmakingWss.handleUpgrade(request, socket, head, (ws) => {
      matchmakingWss.emit('connection', ws, request);
    });
  } else {
    socket.destroy();
  }
});

const PORT = 3000;

// Game State Types
interface Player {
  name: string;
  current: number;
  is_human: boolean;
  discovered: number[];
  sweeps_left: number;
  patch_kits: number;
  traps_left: number;
  decoys_left: number;
  stunned_until: number;
  shield_until: number;
}

interface Room {
  id: string;
  status: 'waiting' | 'active' | 'reconnecting';
  players: Map<string, WebSocket>;
  playerData: Map<string, Player>;
  match_number: number;
  gameState: any;
  logs: any[];
  chat: any[];
  result_summary?: any;
}

const rooms = new Map<string, Room>();
const matchmakingQueue: { clientId: string; playerName: string; ws: WebSocket }[] = [];

// Helper: Broadcast to room
function broadcast(room: Room, message: any) {
  const payload = JSON.stringify(message);
  room.players.forEach((ws) => {
    if (ws.readyState === WebSocket.OPEN) ws.send(payload);
  });
}

// Helper: Create Game State
function createInitialGameState(playerNames: string[]) {
  const nodes: any = {
    "1": { pos: [100, 100], neighbors: [2, 4], server: false, locked: false },
    "2": { pos: [300, 100], neighbors: [1, 3, 5], server: false, locked: false },
    "3": { pos: [500, 100], neighbors: [2, 6], server: true, locked: true },
    "4": { pos: [100, 300], neighbors: [1, 5], server: false, locked: false },
    "5": { pos: [300, 300], neighbors: [2, 4, 6], server: false, locked: false },
    "6": { pos: [500, 300], neighbors: [3, 5], server: false, locked: false },
  };
  const edges = [[1, 2], [2, 3], [1, 4], [4, 5], [2, 5], [5, 6], [3, 6]];
  
  const players = playerNames.map((name, i) => ({
    name,
    current: i === 0 ? 1 : 6,
    is_human: true,
    discovered: i === 0 ? [1, 2, 4] : [6, 5, 3],
    sweeps_left: 3,
    patch_kits: 1,
    traps_left: 2,
    decoys_left: 1,
    stunned_until: 0,
    shield_until: 0
  }));

  return {
    nodes,
    edges,
    players,
    server_id: 3,
    global_unlocks: [],
    winner: null
  };
}

matchmakingWss.on("connection", (ws) => {
  ws.on("message", (data) => {
    const message = JSON.parse(data.toString());
    if (message.type === "queue_join") {
      matchmakingQueue.push({ clientId: message.client_id, playerName: message.player_name, ws });
      ws.send(JSON.stringify({ 
        type: "queue_state", 
        status: "searching", 
        message: "Searching for an opponent...", 
        queued_players: matchmakingQueue.length,
        position: matchmakingQueue.length
      }));

      if (matchmakingQueue.length >= 2) {
        const p1 = matchmakingQueue.shift()!;
        const p2 = matchmakingQueue.shift()!;
        const roomId = `MATCH-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
        
        [p1, p2].forEach(p => {
          if (p.ws.readyState === WebSocket.OPEN) {
            p.ws.send(JSON.stringify({ 
              type: "match_found", 
              session_id: roomId 
            }));
          }
        });
      }
    } else if (message.type === "queue_cancel") {
      const idx = matchmakingQueue.findIndex(q => q.clientId === message.client_id);
      if (idx !== -1) matchmakingQueue.splice(idx, 1);
    }
  });

  ws.on("close", () => {
    const idx = matchmakingQueue.findIndex(q => q.ws === ws);
    if (idx !== -1) matchmakingQueue.splice(idx, 1);
  });
});

wss.on("connection", (ws, req) => {
  const pathname = new URL(req.url!, `http://${req.headers.host}`).pathname;
  const sessionName = decodeURIComponent(pathname.split('/ws/')[1]);
  
  let playerName: string | null = null;

  ws.on("message", (data) => {
    const message = JSON.parse(data.toString());

    if (message.type === "join") {
      playerName = message.player_name;

      if (!rooms.has(sessionName)) {
        rooms.set(sessionName, {
          id: sessionName,
          status: 'waiting',
          players: new Map(),
          playerData: new Map(),
          match_number: 1,
          gameState: null,
          logs: [],
          chat: []
        });
      }

      const room = rooms.get(sessionName)!;
      room.players.set(playerName!, ws);
      
      if (!room.playerData.has(playerName!)) {
        room.playerData.set(playerName!, {
          name: playerName!,
          current: room.playerData.size === 0 ? 1 : 6,
          is_human: true,
          discovered: room.playerData.size === 0 ? [1, 2, 4] : [6, 5, 3],
          sweeps_left: 3,
          patch_kits: 1,
          traps_left: 2,
          decoys_left: 1,
          stunned_until: 0,
          shield_until: 0
        });
      }

      ws.send(JSON.stringify({ 
        type: 'welcome', 
        player_name: playerName,
        room: { 
          status: room.status, 
          match_number: room.match_number,
          connected_players: Array.from(room.players.keys()),
          scoreboard: Array.from(room.playerData.values()).map(p => ({
            name: p.name,
            wins: 0,
            streak: 0,
            connected: true
          }))
        } 
      }));

      if (room.players.size === 2 && room.status === 'waiting') {
        room.status = 'active';
        room.gameState = createInitialGameState(Array.from(room.players.keys()));
        broadcast(room, { type: 'log', lines: ["Systems online. Duel initiated."], kind: "success" });
      }
      
      if (room.gameState) {
        broadcast(room, { type: 'state', state: room.gameState, room: {
          status: room.status,
          match_number: room.match_number,
          connected_players: Array.from(room.players.keys())
        }});
      }
    }

    if (message.type === "command" && sessionName && playerName) {
      const room = rooms.get(sessionName);
      if (!room || !room.gameState) return;

      const cmd = message.text.toLowerCase();
      const player = room.gameState.players.find((p: any) => p.name === playerName);
      
      if (cmd.startsWith("move ")) {
        const targetId = Number(cmd.split(" ")[1]);
        const targetNode = room.gameState.nodes[String(targetId)];
        if (targetNode) {
          player.current = targetId;
          if (!player.discovered.includes(targetId)) player.discovered.push(targetId);
          
          if (targetId === room.gameState.server_id) {
            room.gameState.winner = playerName;
            room.result_summary = {
              headline: "NETWORK BREACHED",
              detail: `${playerName} has successfully infiltrated the core server.`,
              winner: playerName,
              duration_seconds: 45
            };
            broadcast(room, { type: 'log', lines: [`${playerName} HACKED THE SERVER!`], kind: "winner" });
          } else {
            broadcast(room, { type: 'log', lines: [`${playerName} moved to node ${targetId}`], kind: "normal" });
          }
          
          broadcast(room, { type: 'state', state: room.gameState, room: {
            status: room.status,
            match_number: room.match_number,
            connected_players: Array.from(room.players.keys()),
            result_summary: room.result_summary
          }});
        }
      } else if (cmd.startsWith("probe ")) {
        const targetId = cmd.split(" ")[1];
        broadcast(room, { type: 'log', lines: [`${playerName} probed node ${targetId}`], kind: "normal" });
      } else if (cmd === "sweep") {
        broadcast(room, { type: 'log', lines: [`${playerName} initiated a network sweep.`], kind: "success" });
      } else if (cmd === "mission") {
        ws.send(JSON.stringify({ type: 'log', lines: ["Objective: Reach the Server (Node 3) before your rival."], kind: "info" }));
      } else if (cmd === "status") {
        ws.send(JSON.stringify({ type: 'log', lines: [`Current Node: ${player.current}`, `Sweeps Left: ${player.sweeps_left}`], kind: "info" }));
      }
    }

    if (message.type === "control" && message.action === "rematch" && sessionName) {
      const room = rooms.get(sessionName);
      if (room) {
        room.status = 'waiting';
        room.gameState = null;
        room.result_summary = null;
        broadcast(room, { type: 'log', lines: ["Rematch requested. Waiting for opponent..."], kind: "warning" });
        broadcast(room, { type: 'room', room: { status: room.status, match_number: room.match_number + 1, connected_players: Array.from(room.players.keys()) } });
      }
    }

    if (message.type === "chat" && sessionName && playerName) {
      const room = rooms.get(sessionName);
      if (room) {
        const chatMsg = { player_name: playerName, text: message.text, timestamp: Date.now() / 1000 };
        room.chat.push(chatMsg);
        broadcast(room, { type: 'chat', message: chatMsg });
      }
    }
  });

  ws.on("close", () => {
    if (sessionName && playerName) {
      const room = rooms.get(sessionName);
      if (room) {
        room.players.delete(playerName);
        if (room.players.size === 0) rooms.delete(sessionName);
      }
    }
    const idx = matchmakingQueue.findIndex(q => q.ws === ws);
    if (idx !== -1) matchmakingQueue.splice(idx, 1);
  });
});

async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  server.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
