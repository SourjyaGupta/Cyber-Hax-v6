# Cyber Hax v5

Cyber Hax v5 is a web-first multiplayer cyber duel built on `FastAPI + WebSockets`, with the original `pygame` client kept as a legacy/experimental path.

The current focus is browser play:
- fast room creation
- invite-by-link multiplayer
- readable node-map combat
- lightweight session-based replayability

## Product Snapshot

Cyber Hax is a two-player network breach duel. Both players join the same room, read the graph, exploit routes, and race to reach the server core first.

Core design goals:
- browser-first
- low-friction sharing
- readable, cyber-styled UI
- lightweight real-time multiplayer
- easy onboarding for early playtests

## Repository Audit

### Frontend

Web client files:
- `web/index.html`
- `web/styles.css`
- `web/app.js`
- `web/main_music.ogg`
- `web/favicon.svg`

What the web client now does:
- serves a public-facing landing / join experience
- supports create room, join room, and invite-by-link flow
- renders the live node map in SVG
- shows room score, reconnect/waiting state, and match summary
- exposes terminal commands plus a visual command deck
- adds onboarding/help and share UI

Legacy desktop client:
- `cyber_hax.py`
- `network_client.py`

Status:
- still present for compatibility
- no longer the primary launch surface

### Backend

Server files:
- `server_main.py`
- `server_runtime.py`
- `game_core.py`
- `db.py`

What the server now does:
- serves the web app at `/` and `/play`
- serves static assets from `/static`
- exposes websocket multiplayer at `/ws/{session_id}`
- exposes room creation at `/api/rooms/new`
- exposes room metadata at `/api/rooms/{session_id}`
- maintains authoritative per-room game state
- blocks live actions until both players are present
- pauses fair play when an opponent disconnects
- supports rematch and restart room controls
- tracks room win counters and result summaries

### Persistence

Database file:
- `db.py`
- local SQLite database: `cyber_hax.db`

Current DB usage:
- optional match history snapshots
- non-fatal startup if SQLite init fails

### Deployment

Deployment-related files:
- `requirements.txt`
- `render.yaml`
- `Host-Cyber-Hax-Server.bat`
- `Play-Cyber-Hax-Online.bat`

## Current Implemented Features

- Browser-playable multiplayer game served directly from FastAPI
- Room creation and join flow
- Shareable room link and WhatsApp share shortcut
- Reconnect-aware room status
- Waiting-for-opponent state
- Match summary modal
- Room scoreboard with wins and streaks
- Rematch and restart controls
- Music support in browser
- Lightweight synthesized UI sound feedback
- Help modal and landing-page how-to-play guidance
- Cleaner node hover, selection, tooltip, and command queue flow

## Main Files

- `server_runtime.py`: authoritative FastAPI app, room/session logic, API routes, websocket flow
- `server_main.py`: small ASGI entrypoint wrapper
- `game_core.py`: shared node-map rules and command handling
- `web/index.html`: landing page, app shell, modals
- `web/styles.css`: cyber UI styling, layout, responsive behavior
- `web/app.js`: browser multiplayer client, room flow, rendering, sharing, HUD
- `db.py`: optional SQLite persistence for match history
- `cyber_hax.py`: legacy pygame client

## Run Locally

### 1. Install dependencies

```powershell
cd D:\Projects\Cyber\Cyber-Hax-v5
python -m pip install -r requirements.txt
```

### 2. Start the server

```powershell
cd D:\Projects\Cyber\Cyber-Hax-v5
uvicorn server_main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Open the web game

```text
http://127.0.0.1:8000
```

### 4. Local multiplayer test

1. Open the URL in two browser windows or two devices.
2. On one client, click `Create Room`.
3. Copy the room link and open it on the second client.
4. Enter different callsigns and join the same room.

### Optional: legacy pygame client

```powershell
cd D:\Projects\Cyber\Cyber-Hax-v5
python cyber_hax.py
```

## Environment Notes

Current runtime assumptions:
- `PORT` is used automatically by Render or similar hosts
- no extra environment variables are required for local play
- `CYBER_HAX_ALLOWED_ORIGINS` can be set to a comma-separated list of allowed web origins when the frontend is hosted separately from the backend

Current architecture is intentionally simple:
- in-memory room sessions
- SQLite for optional local match history
- no login/auth yet
- no Redis/session broker yet

## Deploy On Render

### Option A: render.yaml

This repo now includes `render.yaml`. Render can use:
- build command: `pip install -r requirements.txt`
- start command: `uvicorn server_main:app --host 0.0.0.0 --port $PORT`

### Option B: manual setup

If you create the service manually:
- Environment: `Python`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn server_main:app --host 0.0.0.0 --port $PORT`

After deploy:
- the web client is served from the same host
- websocket connections automatically use the same origin by default
- room invite links become shareable publicly

### Hosting frontend on itch.io and backend on Render

If you upload the HTML build to itch.io but keep the server on Render:
- keep your Render URL live, for example `https://cyber-hax-server.onrender.com`
- the client will now allow cross-origin room creation from itch.io-style hosts
- the browser client also falls back to the Render server for itch-hosted builds, so `Create Room` works without manual host entry
- if you want to lock this down later, set `CYBER_HAX_ALLOWED_ORIGINS` on Render to your itch.io page origin instead of leaving it open

## Known Limitations

- Rooms are still in-memory only; a full server restart clears active rooms and room scoreboards.
- There is no account system or authentication yet.
- Match history persistence is minimal and local-first.
- There is no anti-cheat or authoritative action replay layer yet.
- The legacy pygame client remains in the repo and could be split into a separate branch later.

## Roadmap

### Current Implemented Features

- Public browser landing page
- Room creation and invite links
- Two-player realtime websocket sessions
- Help/onboarding UX
- Match summary, room score, rematch, restart
- Responsive cyber UI with SVG map rendering

### Next Improvements

- richer node/action animation feedback
- better reconnect resume UX after full page refresh
- stronger room browser / friend challenge flow
- persistent leaderboard and stats
- spectator-safe replay / event timeline

### Future Web Monetization Hooks

- premium visual themes
- season cosmetics / operator skins
- vanity room badges or profile flairs
- hosted tournament brackets / featured rooms

### Future Steam Port Considerations

- keep the shared `game_core.py` rules reusable across clients
- treat the browser build as the live balancing surface
- split desktop packaging into a separate distribution workflow
- add controller/desktop UX only after the web core is stable
