import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Folder, 
  FileText, 
  Github, 
  Activity, 
  Cpu, 
  Zap, 
  ShieldCheck, 
  RefreshCw,
  Search,
  Terminal as TerminalIcon,
  MessageSquare,
  Info,
  Play,
  Pause,
  Copy,
  User,
  Hash,
  Globe,
  Trophy,
  X
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  COMMAND_CARDS, 
  initGameState, 
  GameState, 
  normalizeServerBase, 
  randomCallsign,
  utils,
  inferLogKind,
  bfsDistance,
  nodeFlags,
  viewerStateLabel,
  nextHint
} from './gameLogic';

export default function App() {
  const [state, setState] = useState<GameState>(initGameState());
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [isMusicPlaying, setIsMusicPlaying] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const matchmakingWsRef = useRef<WebSocket | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Sync state to ref for callbacks
  const stateRef = useRef(state);
  useEffect(() => { stateRef.current = state; }, [state]);

  const appendLog = useCallback((message: string | string[], kind: string = '') => {
    const lines = Array.isArray(message) ? message : [message];
    setState(prev => ({
      ...prev,
      logs: [...prev.logs, ...lines.map(l => ({ text: l, kind: kind || inferLogKind(l) }))].slice(-100)
    }));
  }, []);

  const pushToast = useCallback((text: string, tone: string = 'normal') => {
    const id = Math.random().toString();
    setState(prev => ({
      ...prev,
      toasts: [...prev.toasts, { id, text, tone }].slice(-3)
    }));
    setTimeout(() => {
      setState(prev => ({
        ...prev,
        toasts: prev.toasts.filter(t => t.id !== id)
      }));
    }, 3000);
  }, []);

  const connectToServer = useCallback((sessionName?: string) => {
    const s = stateRef.current;
    const session = sessionName || s.sessionName;
    if (!session) return;

    if (wsRef.current) wsRef.current.close();

    const server = normalizeServerBase(s.serverBase);
    const url = `${server}/ws/${encodeURIComponent(session)}`;
    
    appendLog(`[Network] Dialing the live session server...`);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'join',
        player_name: s.playerName || randomCallsign(),
        client_id: s.clientId
      }));
    };

    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === 'welcome') {
        setState(prev => ({ 
          ...prev, 
          connectionStatus: 'connected',
          assignedPlayer: payload.player_name || prev.assignedPlayer,
          room: payload.room || prev.room
        }));
        appendLog(`[Network] Linked as ${payload.player_name || s.playerName}.`, 'success');
        setIsSheetOpen(false);
      } else if (payload.type === 'state') {
        setState(prev => ({ 
          ...prev, 
          gameState: payload.state,
          room: payload.room || prev.room,
          assignedPlayer: payload.player_name || prev.assignedPlayer,
          serverNowBase: payload.state?.server_now || 0,
          clientNowBase: performance.now() / 1000
        }));
      } else if (payload.type === 'chat_history') {
        setState(prev => ({ ...prev, chatMessages: payload.messages || [] }));
      } else if (payload.type === 'chat') {
        setState(prev => ({
          ...prev,
          chatMessages: [...prev.chatMessages, payload.message].slice(-80)
        }));
      } else if (payload.type === 'log') {
        appendLog(payload.lines || []);
      } else if (payload.type === 'error') {
        appendLog(`[Error] ${payload.message}`, 'error');
        pushToast(payload.message, 'error');
      }
    };

    ws.onclose = () => {
      setState(prev => ({ ...prev, connectionStatus: 'disconnected' }));
      appendLog('[Network] Connection closed.', 'warning');
    };
  }, [appendLog, pushToast]);

  const cancelMatchmaking = useCallback((silent: boolean = false) => {
    if (matchmakingWsRef.current && matchmakingWsRef.current.readyState === WebSocket.OPEN) {
      matchmakingWsRef.current.send(JSON.stringify({ type: 'queue_cancel', client_id: stateRef.current.clientId }));
    }
    if (matchmakingWsRef.current) {
      matchmakingWsRef.current.close();
      matchmakingWsRef.current = null;
    }
    setState(prev => ({ 
      ...prev, 
      matchmakingStatus: 'idle',
      matchmakingMessage: "We will create a fresh session and move both players into the same live game as soon as a match is found.",
      matchmakingMeta: "Queue empty. Press find match to search worldwide."
    }));
    if (!silent) pushToast("Matchmaking cancelled", "warning");
  }, [pushToast]);

  const startMatchmaking = useCallback(() => {
    if (matchmakingWsRef.current) cancelMatchmaking(true);
    
    const s = stateRef.current;
    const server = normalizeServerBase(s.serverBase);
    const url = `${server}/ws-matchmaking`;
    
    setState(prev => ({ ...prev, matchmakingStatus: 'searching', matchmakingMessage: "Searching for an online opponent..." }));
    
    const ws = new WebSocket(url);
    matchmakingWsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'queue_join',
        client_id: s.clientId,
        player_name: s.playerName || randomCallsign()
      }));
    };

    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === 'queue_state') {
        setState(prev => ({
          ...prev,
          matchmakingStatus: payload.status,
          matchmakingMessage: payload.message || prev.matchmakingMessage,
          matchmakingMeta: `Queued: ${payload.queued_players} | Position: ${payload.position}`
        }));
      } else if (payload.type === 'match_found') {
        const sessionId = payload.session_id;
        setState(prev => ({ ...prev, sessionName: sessionId, matchmakingStatus: 'matched' }));
        pushToast("Match found! Joining...", "success");
        connectToServer(sessionId);
      } else if (payload.type === 'error') {
        pushToast(payload.message, "error");
        cancelMatchmaking(true);
      }
    };

    ws.onclose = () => {
      if (stateRef.current.matchmakingStatus === 'searching') {
        setState(prev => ({ ...prev, matchmakingStatus: 'idle' }));
        pushToast("Matchmaking connection lost", "error");
      }
    };
  }, [cancelMatchmaking, connectToServer, pushToast]);

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault();
    connectToServer();
  };

  const toggleMusic = () => {
    if (!audioRef.current) return;
    if (isMusicPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch(() => {
        pushToast("Click again to enable audio", "warning");
      });
    }
    setIsMusicPlaying(!isMusicPlaying);
  };

  useEffect(() => {
    // Auto-connect to a default session on mount
    const defaultSession = 'LOBBY-' + Math.random().toString(36).substring(2, 6).toUpperCase();
    setState(prev => ({ ...prev, sessionName: defaultSession, playerName: randomCallsign() }));
    
    // Give the server a moment to start if needed
    const timer = setTimeout(() => {
      connectToServer(defaultSession);
    }, 1000);
    
    return () => {
      clearTimeout(timer);
      if (wsRef.current) wsRef.current.close();
      if (matchmakingWsRef.current) matchmakingWsRef.current.close();
    };
  }, [connectToServer]);

  // SVG Rendering Logic
  useEffect(() => {
    if (!svgRef.current || !state.gameState) return;
    const svg = svgRef.current;
    svg.innerHTML = ''; // Clear

    const { nodes, edges, players } = state.gameState;
    if (!nodes) return;

    const viewer = players?.find((p: any) => p.name === state.playerName);
    const opponent = players?.find((p: any) => p.is_human && p.name !== state.playerName);
    const visible = new Set([...(viewer?.discovered || []), ...(viewer?.reveal_nodes || [])]);

    const edgeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const signalLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const nodeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");

    // Draw Edges
    edges?.forEach(([a, b]: [number, number]) => {
      const sA = String(a);
      const sB = String(b);
      if (!visible.has(a) || !visible.has(b)) return;
      const n1 = nodes[sA];
      const n2 = nodes[sB];
      if (!n1 || !n2) return;
      
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", n1.pos[0].toString());
      line.setAttribute("y1", n1.pos[1].toString());
      line.setAttribute("x2", n2.pos[0].toString());
      line.setAttribute("y2", n2.pos[1].toString());
      const isActive = state.selectedNode === sA || state.selectedNode === sB || viewer?.current === a || viewer?.current === b;
      line.setAttribute("class", `edge-line ${isActive ? 'active' : ''}`);
      edgeLayer.appendChild(line);

      // Signal Dot
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("r", "3");
      dot.setAttribute("class", "signal-dot");
      signalLayer.appendChild(dot);
      // We'll animate these in a separate loop or with CSS if possible, 
      // but for now let's just place them at start.
    });

    // Draw Nodes
    Object.entries(nodes).forEach(([id, node]: [string, any]) => {
      if (!visible.has(Number(id))) return;

      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("class", "node-group");
      group.style.cursor = "pointer";
      
      const isCurrent = Number(id) === Number(viewer?.current);
      const isOpponent = Number(id) === Number(opponent?.current);
      const isSelected = id === state.selectedNode;
      const unlocked = (state.gameState.global_unlocks || []).includes(Number(id));

      // Halo
      if (isCurrent || isSelected) {
        const halo = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        halo.setAttribute("cx", node.pos[0].toString());
        halo.setAttribute("cy", node.pos[1].toString());
        halo.setAttribute("r", isCurrent ? "28" : "24");
        halo.setAttribute("class", "node-halo");
        group.appendChild(halo);
      }
      if (isOpponent) {
        const rivalHalo = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        rivalHalo.setAttribute("cx", node.pos[0].toString());
        rivalHalo.setAttribute("cy", node.pos[1].toString());
        rivalHalo.setAttribute("r", "26");
        rivalHalo.setAttribute("class", "node-halo rival");
        group.appendChild(rivalHalo);
      }

      // Ring
      const ring = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      ring.setAttribute("cx", node.pos[0].toString());
      ring.setAttribute("cy", node.pos[1].toString());
      ring.setAttribute("r", node.server ? "16" : "12");
      ring.setAttribute("class", "node-ring");
      group.appendChild(ring);

      // Core
      const core = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      core.setAttribute("cx", node.pos[0].toString());
      core.setAttribute("cy", node.pos[1].toString());
      core.setAttribute("r", node.server ? "10" : "8");
      core.setAttribute("class", "node-core");
      
      let color = "#eef6ff";
      if (node.server) color = "var(--color-node-server)";
      else if (node.locked && !unlocked) color = "var(--color-node-locked)";
      else if (node.mine) color = "var(--color-node-mine)";
      core.style.fill = color;
      group.appendChild(core);
      
      // Label
      const labelBg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      labelBg.setAttribute("x", (node.pos[0] - 12).toString());
      labelBg.setAttribute("y", (node.pos[1] - 32).toString());
      labelBg.setAttribute("width", "24");
      labelBg.setAttribute("height", "14");
      labelBg.setAttribute("rx", "6");
      labelBg.setAttribute("class", "node-label-bg");
      group.appendChild(labelBg);

      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", node.pos[0].toString());
      text.setAttribute("y", (node.pos[1] - 22).toString());
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("class", "node-label");
      text.textContent = id;
      group.appendChild(text);

      // Occupant Badge
      if (isCurrent || isOpponent) {
        const badge = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        badge.setAttribute("x", (node.pos[0] + 10).toString());
        badge.setAttribute("y", (node.pos[1] - 20).toString());
        badge.setAttribute("width", "18");
        badge.setAttribute("height", "14");
        badge.setAttribute("rx", "6");
        badge.setAttribute("class", `occupant-badge ${isOpponent ? 'rival' : ''}`);
        group.appendChild(badge);

        const bText = document.createElementNS("http://www.w3.org/2000/svg", "text");
        bText.setAttribute("x", (node.pos[0] + 19).toString());
        bText.setAttribute("y", (node.pos[1] - 9).toString());
        bText.setAttribute("text-anchor", "middle");
        bText.setAttribute("class", "occupant-text");
        bText.textContent = (isCurrent ? viewer.name : opponent.name).slice(0, 1).toUpperCase();
        group.appendChild(bText);
      }

      group.onclick = () => {
        setState(prev => ({ ...prev, selectedNode: id }));
        if (wsRef.current && viewer) {
          const currentNode = nodes[String(viewer.current)];
          const isAdjacent = currentNode?.neighbors?.includes(Number(id));
          const isUnlocked = !node.locked || (stateRef.current.gameState.global_unlocks || []).includes(Number(id));
          
          const cmd = (isAdjacent && isUnlocked) ? `move ${id}` : `probe ${id}`;
          wsRef.current.send(JSON.stringify({ type: 'command', text: cmd }));
          appendLog(`> ${cmd}`, 'command');
        }
      };

      nodeLayer.appendChild(group);
    });

    svg.appendChild(edgeLayer);
    svg.appendChild(signalLayer);
    svg.appendChild(nodeLayer);

  }, [state.gameState, state.playerName, state.selectedNode]);

  // Auto-scroll logs and chat
  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [state.logs]);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [state.chatMessages]);

  const [isCyberDeck, setIsCyberDeck] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

  useEffect(() => {
    if (state.room?.result_summary) {
      setShowSummary(true);
    } else {
      setShowSummary(false);
    }
  }, [state.room?.result_summary]);

  return (
    <div className={`flex flex-col h-screen overflow-hidden ${isCyberDeck ? 'bg-black text-white' : 'bg-bg-main'}`}>
      <audio ref={audioRef} src="/main_music.ogg" loop />

      {/* Summary Modal */}
      <AnimatePresence>
        {showSummary && state.room?.result_summary && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-md p-4 md:p-6"
          >
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="w-full max-w-md bg-white rounded-3xl shadow-2xl p-6 md:p-8 text-center"
            >
              <div className="w-16 h-16 md:w-20 md:h-20 bg-accent-soft rounded-full mx-auto mb-4 md:mb-6 flex items-center justify-center">
                <Trophy className="w-8 h-8 md:w-10 md:h-10 text-accent-primary" />
              </div>
              <h2 className="text-2xl md:text-3xl font-bold tracking-tight mb-2 text-black">{state.room.result_summary.headline}</h2>
              <p className="text-sm md:text-base text-text-secondary mb-6 md:mb-8">{state.room.result_summary.detail}</p>
              
              <div className="grid grid-cols-2 gap-3 md:gap-4 mb-6 md:mb-8">
                <div className="p-3 md:p-4 bg-[#f9f9f9] rounded-2xl border border-border-subtle">
                  <div className="text-[9px] md:text-[10px] uppercase tracking-widest font-bold text-text-muted mb-1">Winner</div>
                  <div className="text-base md:text-lg font-bold truncate text-black">{state.room.result_summary.winner}</div>
                </div>
                <div className="p-3 md:p-4 bg-[#f9f9f9] rounded-2xl border border-border-subtle">
                  <div className="text-[9px] md:text-[10px] uppercase tracking-widest font-bold text-text-muted mb-1">Duration</div>
                  <div className="text-base md:text-lg font-bold text-black">{state.room.result_summary.duration_seconds}s</div>
                </div>
              </div>

              <div className="flex flex-col gap-3">
                <button 
                  onClick={() => {
                    if (wsRef.current) wsRef.current.send(JSON.stringify({ type: 'control', action: 'rematch' }));
                  }}
                  className="w-full bg-black text-white py-4 rounded-2xl font-bold text-sm hover:bg-gray-800 transition-all"
                >
                  Vote for Rematch
                </button>
                <button 
                  onClick={() => setShowSummary(false)}
                  className="w-full bg-white text-black border border-border-subtle py-4 rounded-2xl font-bold text-sm hover:bg-bg-secondary transition-all"
                >
                  Close Summary
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Header */}
      <header className={`h-16 border-b flex items-center justify-between px-4 md:px-6 shrink-0 z-20 ${isCyberDeck ? 'bg-black border-white/10' : 'bg-white border-border-subtle'}`}>
        <div className="flex items-center gap-2 md:gap-3">
          <div className={`w-7 h-7 md:w-8 md:h-8 rounded-md flex items-center justify-center ${isCyberDeck ? 'bg-white' : 'bg-black'}`}>
            <div className={`w-3.5 h-3.5 md:w-4 md:h-4 rounded-sm rotate-45 ${isCyberDeck ? 'bg-black' : 'bg-white'}`} />
          </div>
          <span className="font-semibold text-sm md:text-base tracking-tight truncate max-w-[100px] md:max-w-none">Cyber Hax v5</span>
        </div>
        
        <div className="flex items-center gap-2 md:gap-4">
          <button 
            onClick={toggleMusic}
            className={`flex items-center gap-2 px-2 md:px-3 py-1.5 rounded-lg text-[10px] md:text-xs font-medium transition-all ${
              isCyberDeck ? 'bg-white/10 hover:bg-white/20' : 'bg-[#f0f0f0] hover:bg-[#e0e0e0]'
            }`}
          >
            {isMusicPlaying ? <Pause className="w-3 h-3 md:w-3.5 md:h-3.5" /> : <Play className="w-3 h-3 md:w-3.5 md:h-3.5" />}
            <span className="hidden sm:inline">{isMusicPlaying ? 'Mute' : 'Play Music'}</span>
          </button>

          <div className={`hidden sm:block h-6 md:h-8 w-[1px] ${isCyberDeck ? 'bg-white/10' : 'bg-border-subtle'}`} />

          <div className="hidden sm:flex items-center gap-2 px-2 md:px-3 py-1.5 rounded-lg bg-[#f0f0f0] text-[10px] md:text-xs font-medium">
            <div className={`w-1.5 h-1.5 md:w-2 md:h-2 rounded-full ${state.connectionStatus === 'connected' ? 'bg-cyber-success animate-pulse' : 'bg-cyber-danger'}`} />
            <span className="text-text-secondary uppercase tracking-wider text-[9px] md:text-[10px]">
              {state.connectionStatus === 'connected' ? 'Online' : 'Offline'}
            </span>
          </div>

          <div className={`h-6 md:h-8 w-[1px] ${isCyberDeck ? 'bg-white/10' : 'bg-border-subtle'}`} />

          <button 
            onClick={() => setIsCyberDeck(!isCyberDeck)}
            className={`flex items-center gap-2 px-2 md:px-3 py-1.5 rounded-lg text-[10px] md:text-xs font-medium transition-all ${
              isCyberDeck ? 'bg-white text-black' : 'bg-black text-white'
            }`}
          >
            <TerminalIcon className="w-3 h-3 md:w-3.5 md:h-3.5" />
            <span className="hidden sm:inline">{isCyberDeck ? 'Standard' : 'Cyber Deck'}</span>
          </button>
        </div>
      </header>

      {/* Workspace */}
      <div className={`flex-1 flex flex-col md:grid overflow-hidden transition-all duration-500 ${isCyberDeck ? 'md:grid-cols-[1fr_380px] p-2 md:p-4 gap-2 md:gap-4' : 'md:grid-cols-[280px_1fr_320px]'}`}>
        {/* Left Sidebar: Room & Stats (Hidden on Mobile or in Cyber Deck) */}
        {!isCyberDeck && (
          <aside className="hidden md:flex bg-white border-r border-border-subtle p-5 flex-col gap-6 overflow-y-auto">
            <div>
              <div className="sidebar-title">Operator Status</div>
              <div className="space-y-4">
                <div className="flex flex-col gap-1">
                  <span className="text-lg font-semibold">{state.playerName || 'Standby'}</span>
                  <span className="text-[11px] text-text-muted uppercase tracking-wider flex items-center gap-1">
                    <User className="w-3 h-3" /> Callsign
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1">
                    <span className="text-base font-medium">{state.gameState?.players?.length || 0} / 2</span>
                    <span className="text-[10px] text-text-muted uppercase tracking-wider">Operators</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-base font-medium">#{state.room?.match_number || 1}</span>
                    <span className="text-[10px] text-text-muted uppercase tracking-wider">Match</span>
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-sm font-medium">{viewerStateLabel(state.gameState?.players?.find((p: any) => p.name === state.playerName), state.room, state.gameState, state)}</span>
                  <span className="text-[10px] text-text-muted uppercase tracking-wider">Current State</span>
                </div>
              </div>
            </div>

            <div>
              <div className="sidebar-title">Scoreboard</div>
              <div className="space-y-2">
                {state.room?.scoreboard ? state.room.scoreboard.map((entry: any) => (
                  <div key={entry.name} className="flex items-center justify-between p-2 bg-[#f9f9f9] rounded-lg border border-border-subtle">
                    <div className="flex flex-col">
                      <span className="text-sm font-medium truncate">{entry.name}</span>
                      <span className="text-[10px] text-text-muted">Streak {entry.streak}</span>
                    </div>
                    <span className="text-sm font-bold">{entry.wins}</span>
                  </div>
                )) : (
                  <div className="text-[13px] text-text-muted italic">No scores recorded yet.</div>
                )}
              </div>
            </div>

            <div className="mt-auto">
              <button 
                onClick={() => setIsSheetOpen(true)}
                className="action-btn flex items-center justify-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Switch Room
              </button>
            </div>
          </aside>
        )}

        {/* Main Stage: Network Graph */}
        <main className={`flex flex-col gap-2 md:gap-4 overflow-hidden transition-all duration-500 ${isCyberDeck ? 'bg-[#0a0a0a] md:border md:border-white/10 md:rounded-2xl p-4 md:p-6' : 'p-4 md:p-6'}`}>
          <div className="flex items-center justify-between">
            <div>
              <h2 className={`text-lg md:text-xl font-semibold tracking-tight ${isCyberDeck ? 'text-white' : 'text-black'}`}>Network Board</h2>
              <p className={`text-[11px] md:text-[13px] ${isCyberDeck ? 'text-white/50' : 'text-text-secondary'}`}>
                {nextHint(state.gameState?.players?.find((p: any) => p.name === state.playerName), state.room, state.gameState, state.selectedNode)}
              </p>
            </div>
            <div className="hidden sm:flex gap-2">
              <span className={`tag ${isCyberDeck ? 'bg-white/10 text-white/70' : ''}`}>REAL-TIME</span>
              <span className={`tag ${isCyberDeck ? 'bg-white/10 text-white/70' : ''}`}>MULTIPLAYER</span>
            </div>
          </div>

          <div className={`board-stage flex-1 relative min-h-[300px] ${isCyberDeck ? '!bg-transparent !border-white/5' : ''}`}>
            <svg 
              ref={svgRef} 
              viewBox="0 0 780 720" 
              className={`w-full h-full ${isCyberDeck ? 'invert brightness-200 contrast-150' : ''}`}
              preserveAspectRatio="xMidYMid meet"
            />
            {!state.gameState && (
              <div className={`absolute inset-0 flex items-center justify-center backdrop-blur-sm ${isCyberDeck ? 'bg-black/40' : 'bg-white/80'}`}>
                <div className="text-center p-6">
                  <Activity className={`w-10 h-10 md:w-12 md:h-12 mx-auto mb-4 animate-pulse ${isCyberDeck ? 'text-white/30' : 'text-text-muted'}`} />
                  <p className={`text-xs md:text-sm font-medium ${isCyberDeck ? 'text-white/50' : ''}`}>Awaiting network connection...</p>
                </div>
              </div>
            )}
          </div>
          
          <div className={`flex items-center justify-center gap-3 md:gap-6 text-[9px] md:text-[11px] uppercase tracking-widest py-2 ${isCyberDeck ? 'text-white/40' : 'text-text-muted'}`}>
            <div className="flex items-center gap-1.5">
              <div className={`w-1.5 h-1.5 md:w-2 md:h-2 rounded-full ${isCyberDeck ? 'bg-white' : 'bg-black'}`} /> You
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 md:w-2 md:h-2 rounded-full bg-node-rival" /> Rival
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 md:w-2 md:h-2 rounded-full bg-node-server" /> Server
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 md:w-2 md:h-2 rounded-full border border-node-locked" /> Locked
            </div>
          </div>
        </main>

        {/* Right Sidebar: Intel & Terminal */}
        <aside className={`flex flex-col overflow-hidden transition-all duration-500 h-[400px] md:h-auto ${isCyberDeck ? 'bg-[#0a0a0a] md:border md:border-white/10 md:rounded-2xl' : 'bg-white border-t md:border-t-0 md:border-l border-border-subtle'}`}>
          {/* Intel Section */}
          <div className={`p-5 border-b shrink-0 ${isCyberDeck ? 'border-white/10' : 'border-border-subtle'}`}>
            <div className="sidebar-title">Node Intel</div>
            <div className={`card !p-4 min-h-[100px] flex flex-col justify-center ${isCyberDeck ? '!bg-white/5 !border-white/10' : ''}`}>
              {state.selectedNode ? (
                <div>
                  <div className={`font-bold text-lg mb-1 ${isCyberDeck ? 'text-white' : 'text-black'}`}>Node {state.selectedNode}</div>
                  <div className="flex flex-wrap gap-1 mb-2">
                    {nodeFlags(state.selectedNode, state.gameState).map((flag: any) => (
                      <span key={flag.label} className={`tag ${flag.className}`}>{flag.label}</span>
                    ))}
                    {nodeFlags(state.selectedNode, state.gameState).length === 0 && <span className="tag">Stable</span>}
                  </div>
                  <div className="text-[12px] space-y-1">
                    <p className={isCyberDeck ? 'text-white/70' : 'text-text-secondary'}>
                      Distance to Server: {bfsDistance(state.gameState?.nodes, state.gameState?.players?.find((p: any) => p.name === state.playerName)?.current, state.gameState?.server_id) ?? 'Unknown'}
                    </p>
                    <p className={isCyberDeck ? 'text-white/70' : 'text-text-secondary'}>
                      Links: {state.gameState?.nodes?.[state.selectedNode]?.neighbors?.join(', ') || 'None'}
                    </p>
                  </div>
                </div>
              ) : (
                <div className={`text-[13px] italic flex items-center gap-2 ${isCyberDeck ? 'text-white/30' : 'text-text-muted'}`}>
                  <Info className="w-4 h-4" /> Select a node on the board to inspect.
                </div>
              )}
            </div>
          </div>

          {/* Terminal & Chat Tabs */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className={`flex border-b shrink-0 ${isCyberDeck ? 'border-white/10' : 'border-border-subtle'}`}>
              <button className={`flex-1 py-3 text-[11px] font-bold uppercase tracking-wider border-b-2 ${isCyberDeck ? 'border-white text-white' : 'border-black'}`}>Terminal</button>
              <button className={`flex-1 py-3 text-[11px] font-bold uppercase tracking-wider ${isCyberDeck ? 'text-white/40 hover:text-white' : 'text-text-muted hover:text-black'} transition-colors`}>Chat</button>
            </div>
            
            <div className={`flex-1 p-4 overflow-y-auto font-mono text-[13px] ${isCyberDeck ? 'bg-black text-white/80' : 'bg-[#fafafa]'}`}>
              {state.logs.map((log, i) => (
                <div key={i} className={`log-line ${log.kind} ${isCyberDeck && log.kind === 'normal' ? 'text-white/70' : ''}`}>
                  {log.text}
                </div>
              ))}
              <div ref={logEndRef} />
            </div>

            {/* Command Deck (Only in Cyber Deck) */}
            {isCyberDeck && (
              <div className="p-4 border-t border-white/10 bg-black/50 overflow-x-auto">
                <div className="flex gap-2 pb-2">
                  {COMMAND_CARDS.filter(c => c.mode === 'send').map(card => (
                    <button 
                      key={card.command}
                      onClick={() => {
                        if (wsRef.current) {
                          wsRef.current.send(JSON.stringify({ type: 'command', text: card.command }));
                          appendLog(`> ${card.command}`, 'command');
                        }
                      }}
                      className="shrink-0 px-3 py-2 bg-white/10 hover:bg-white/20 border border-white/10 rounded-lg text-[11px] font-mono text-white transition-colors"
                    >
                      {card.command}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className={`p-4 border-t bg-white ${isCyberDeck ? 'bg-black border-white/10' : 'border-border-subtle'}`}>
              <form 
                onSubmit={(e) => {
                  e.preventDefault();
                  const input = (e.currentTarget.elements.namedItem('cmd') as HTMLInputElement);
                  if (input.value && wsRef.current) {
                    wsRef.current.send(JSON.stringify({ type: 'command', text: input.value }));
                    appendLog(`> ${input.value}`, 'command');
                    input.value = '';
                  }
                }}
                className="relative"
              >
                <TerminalIcon className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${isCyberDeck ? 'text-white/30' : 'text-text-muted'}`} />
                <input 
                  name="cmd"
                  type="text" 
                  placeholder="Enter command..."
                  className={`w-full pl-9 pr-4 py-2.5 rounded-lg text-[13px] outline-none transition-all ${
                    isCyberDeck ? 'bg-white/10 text-white placeholder:text-white/20 focus:ring-1 focus:ring-white/30' : 'bg-[#f0f0f0] focus:ring-1 focus:ring-black'
                  }`}
                />
              </form>
            </div>
          </div>
        </aside>
      </div>

      {/* Join Sheet Overlay */}
      <AnimatePresence>
        {isSheetOpen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-white/90 backdrop-blur-md p-4 md:p-6"
          >
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="w-full max-w-md bg-white border border-border-subtle rounded-3xl shadow-2xl p-6 md:p-8 overflow-y-auto max-h-[90vh]"
            >
              <div className="mb-6 md:mb-8 text-center">
                <div className="w-12 h-12 md:w-16 md:h-16 bg-black rounded-2xl mx-auto mb-4 flex items-center justify-center">
                  <div className="w-6 h-6 md:w-8 md:h-8 bg-white rounded-md rotate-45" />
                </div>
                <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Cyber Hax v5</h1>
                <p className="text-sm md:text-base text-text-secondary mt-2">Enter the network duel.</p>
              </div>

              <div className="space-y-4 md:space-y-6">
                {/* Matchmaking Section */}
                <div className="p-4 md:p-5 bg-accent-soft/30 rounded-2xl border border-accent-soft">
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-[9px] md:text-[10px] font-bold uppercase tracking-widest ${state.matchmakingStatus === 'searching' ? 'text-accent-primary animate-pulse' : 'text-text-muted'}`}>
                      {state.matchmakingStatus.toUpperCase()}
                    </span>
                    {state.matchmakingStatus === 'searching' && (
                      <button onClick={() => cancelMatchmaking()} className="text-[9px] md:text-[10px] font-bold text-red-500 hover:underline">CANCEL</button>
                    )}
                  </div>
                  <p className="text-xs md:text-sm font-semibold mb-1">{state.matchmakingMessage}</p>
                  <p className="text-[10px] md:text-[11px] text-text-muted leading-relaxed">{state.matchmakingMeta}</p>
                  <button 
                    onClick={startMatchmaking}
                    disabled={state.matchmakingStatus === 'searching'}
                    className="w-full mt-3 md:mt-4 bg-black text-white py-3 md:py-3.5 rounded-xl font-bold text-xs md:text-sm hover:bg-gray-800 transition-all disabled:opacity-50 shadow-lg shadow-black/5"
                  >
                    {state.matchmakingStatus === 'searching' ? 'Searching...' : 'Find Online Match'}
                  </button>
                </div>

                <div className="relative">
                  <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-border-subtle"></div></div>
                  <div className="relative flex justify-center text-[10px] uppercase tracking-widest font-bold text-text-muted"><span className="bg-white px-3">or join private</span></div>
                </div>

                <form onSubmit={handleJoin} className="space-y-5">
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold uppercase text-text-muted tracking-wider ml-1">Callsign</label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                      <input 
                        type="text" 
                        value={state.playerName}
                        onChange={(e) => setState(prev => ({ ...prev, playerName: e.target.value }))}
                        placeholder="Operator-101"
                        className="w-full pl-9 pr-4 py-3 bg-[#f0f0f0] border-none rounded-xl text-sm focus:ring-1 focus:ring-black outline-none transition-all"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold uppercase text-text-muted tracking-wider ml-1">Room Code</label>
                    <div className="relative">
                      <Hash className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                      <input 
                        type="text" 
                        value={state.sessionName}
                        onChange={(e) => setState(prev => ({ ...prev, sessionName: e.target.value }))}
                        placeholder="A1B2C3"
                        className="w-full pl-9 pr-4 py-3 bg-[#f0f0f0] border-none rounded-xl text-sm focus:ring-1 focus:ring-black outline-none transition-all"
                      />
                    </div>
                  </div>

                  <div className="pt-2">
                    <button type="submit" className="action-btn !py-4 text-base shadow-lg shadow-black/5">
                      Connect to Session
                    </button>
                  </div>
                  
                  <div className="text-center">
                    <button 
                      type="button"
                      onClick={() => setState(prev => ({ ...prev, sessionName: Math.random().toString(36).substring(2, 8).toUpperCase() }))}
                      className="text-[12px] text-text-muted hover:text-black transition-colors font-medium"
                    >
                      Generate random room code
                    </button>
                  </div>
                </form>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toasts */}
      <div className="fixed top-20 right-6 z-[60] flex flex-col gap-2">
        {state.toasts.map(toast => (
          <motion.div 
            key={toast.id}
            initial={{ x: 100, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 100, opacity: 0 }}
            className={`px-4 py-3 rounded-xl shadow-lg border text-sm font-medium ${
              toast.tone === 'success' ? 'bg-white border-cyber-success text-cyber-success' :
              toast.tone === 'error' ? 'bg-white border-cyber-danger text-cyber-danger' :
              'bg-white border-border-subtle text-text-primary'
            }`}
          >
            {toast.text}
          </motion.div>
        ))}
      </div>
    </div>
  );
}
