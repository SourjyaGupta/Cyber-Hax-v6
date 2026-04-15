from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from io import StringIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

from db import DB_READY, MatchHistory, SessionLocal
from game_core import (
    add_human_player,
    build_new_game,
    handle_command,
    normalize_player_name,
    serialize_state,
    update_temporary_effects,
)

app = FastAPI(title="Cyber Hax")
logger = logging.getLogger("cyber_hax.server")
CORS_ORIGIN_REGEX = r"https://.*(itch\.io|ssl\.hwcdn\.net|github\.io|netlify\.app)$|http://localhost(:\d+)?|http://127\.0\.0\.1(:\d+)?"

# CORS is needed for itch.io-hosted HTML builds calling the Render API over fetch().
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

SESSION_MAX_HUMANS = 2
SESSION_AI_COUNT = 0
TICK_INTERVAL = 0.5
IDLE_SESSION_TIMEOUT = 300
ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOM_CODE_LENGTH = 6
INFO_ONLY_COMMANDS = {"help", "status", "log"}
CONTROL_COMMANDS = {"rematch", "restart"}
MAX_CHAT_HISTORY = 80
MAX_CHAT_LENGTH = 280
MATCHMAKING_STALE_TIMEOUT = 45.0
MATCHMAKING_ASSIGNMENT_TTL = 90.0
MATCHMAKING_CLEANUP_INTERVAL = 6.0
MATCHMAKING_ACTION_COOLDOWN = 1.2

sessions: dict[str, dict[str, Any]] = {}
# Public matchmaking stays separate from room sockets so it can hand players
# into the existing authoritative session flow only after a server-side match is locked.
matchmaking_queue: list[dict[str, Any]] = []
matchmaking_index: dict[str, dict[str, Any]] = {}
matchmaking_socket_index: dict[WebSocket, str] = {}
matchmaking_assignments: dict[str, dict[str, Any]] = {}
matchmaking_last_action: dict[str, float] = {}
matchmaking_lock = asyncio.Lock()
matchmaking_cleanup_task: asyncio.Task | None = None

PUBLIC_WEB_FILES = {
    "app.js",
    "styles.css",
    "main_music.ogg",
    "favicon.svg",
}


def _normalize_client_id(raw_value: Any) -> str:
    clean = "".join(ch for ch in str(raw_value or "") if ch.isalnum() or ch in "-_")
    if clean:
        return clean[:64]
    return secrets.token_hex(12)


def _websocket_is_open(websocket: WebSocket | None) -> bool:
    if websocket is None:
        return False
    return (
        websocket.client_state == WebSocketState.CONNECTED
        and websocket.application_state == WebSocketState.CONNECTED
    )


def _public_web_file(filename: str) -> FileResponse:
    path = WEB_DIR / filename
    if filename not in PUBLIC_WEB_FILES or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)


@app.on_event("startup")
async def startup_event() -> None:
    global matchmaking_cleanup_task
    if matchmaking_cleanup_task is None or matchmaking_cleanup_task.done():
        matchmaking_cleanup_task = asyncio.create_task(_matchmaking_cleanup_loop())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global matchmaking_cleanup_task
    task = matchmaking_cleanup_task
    matchmaking_cleanup_task = None
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/play")
async def play() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/app.js")
async def web_app_js() -> FileResponse:
    return _public_web_file("app.js")


@app.get("/styles.css")
async def web_styles() -> FileResponse:
    return _public_web_file("styles.css")


@app.get("/main_music.ogg")
async def web_music() -> FileResponse:
    return _public_web_file("main_music.ogg")


@app.get("/favicon.svg")
async def web_favicon() -> FileResponse:
    return _public_web_file("favicon.svg")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "sessions": len(sessions),
        "rooms": sorted(sessions.keys()),
        "queued_players": len(matchmaking_queue),
    }


@app.get("/api/test")
async def test() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/rooms/new")
async def create_room(request: Request) -> dict[str, Any]:
    try:
        room_id = _generate_room_code()
        _get_or_create_session(room_id, match_type="private")
        return {
            "room_id": room_id,
            "join_url": _build_join_url(request, room_id),
        }
    except Exception as exc:
        logger.exception("Failed to create room")
        raise HTTPException(status_code=500, detail={"error": "room_creation_failed", "message": str(exc)}) from exc


@app.get("/api/rooms/{session_id}")
async def room_info(session_id: str, request: Request) -> dict[str, Any]:
    session = sessions.get(session_id)
    return {
        "exists": session is not None,
        "room": _serialize_room(session_id, session) if session is not None else None,
        "join_url": _build_join_url(request, session_id),
    }


def _build_join_url(request: Request, session_id: str) -> str:
    return f"{str(request.base_url).rstrip('/')}/play?session={session_id}"


def _blank_score_entry() -> dict[str, int]:
    return {
        "wins": 0,
        "games": 0,
        "streak": 0,
        "best_streak": 0,
    }


def _create_session(session_id: str, match_type: str = "private") -> dict[str, Any]:
    return {
        "id": session_id,
        "match_type": match_type,
        "game": build_new_game(max_humans=SESSION_MAX_HUMANS, num_ai=SESSION_AI_COUNT),
        "clients": {},
        "lock": asyncio.Lock(),
        "task": None,
        "log_cursor": 0,
        "saved_match": False,
        "result_recorded": False,
        "idle_since": None,
        "scoreboard": {},
        "registered_players": [],
        "match_number": 1,
        "last_winner": None,
        "result_summary": None,
        "rematch_votes": set(),
        "chat_history": [],
        "created_at": time.time(),
        "match_started_at": None,
    }


def _get_or_create_session(session_id: str, match_type: str = "private") -> dict[str, Any]:
    session = sessions.get(session_id)
    if session is None:
        session = _create_session(session_id, match_type=match_type)
        sessions[session_id] = session
        session["task"] = asyncio.create_task(_session_loop(session_id))
    elif match_type and session.get("match_type") != "public":
        session["match_type"] = match_type
    return session


def _generate_room_code() -> str:
    while True:
        code = "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))
        if code not in sessions:
            return code


def _connected_player_names(session: dict[str, Any]) -> set[str]:
    return {name for name in session["clients"].values()}


def _ensure_score_entry(session: dict[str, Any], player_name: str) -> dict[str, int]:
    if player_name not in session["scoreboard"]:
        session["scoreboard"][player_name] = _blank_score_entry()
    return session["scoreboard"][player_name]


def _registered_human_names(session: dict[str, Any]) -> list[str]:
    return list(session["registered_players"])


def _session_status(session: dict[str, Any]) -> str:
    registered = _registered_human_names(session)
    connected = _connected_player_names(session)
    if session["game"].winner:
        return "finished"
    if len(registered) < SESSION_MAX_HUMANS:
        return "waiting"
    if len(connected) < SESSION_MAX_HUMANS:
        return "reconnecting"
    return "live"


def _room_notice(session: dict[str, Any]) -> str:
    status = _session_status(session)
    match_type = session.get("match_type", "private")
    if status == "waiting":
        if match_type == "public":
            return "Public match found. Waiting for the second operator to finish linking into the duel."
        return "Waiting for a second operator. Share the room link to begin the duel."
    if status == "reconnecting":
        return "Opponent offline. The duel is paused until both operators reconnect."
    if status == "finished":
        return "Match complete. Vote rematch to keep the room score or restart to reset the room."
    if match_type == "public":
        return "Live public duel. You were matched with an unknown operator."
    return "Live duel. Both operators can act at any time."


def _serialize_room(session_id: str, session: dict[str, Any]) -> dict[str, Any]:
    connected = _connected_player_names(session)
    scoreboard = []
    for player_name in _registered_human_names(session):
        stats = _ensure_score_entry(session, player_name)
        scoreboard.append(
            {
                "name": player_name,
                "wins": stats["wins"],
                "games": stats["games"],
                "streak": stats["streak"],
                "best_streak": stats["best_streak"],
                "connected": player_name in connected,
            }
        )

    return {
        "session_id": session_id,
        "match_type": session.get("match_type", "private"),
        "status": _session_status(session),
        "notice": _room_notice(session),
        "player_capacity": SESSION_MAX_HUMANS,
        "registered_players": _registered_human_names(session),
        "connected_players": sorted(connected),
        "scoreboard": scoreboard,
        "match_number": session["match_number"],
        "last_winner": session["last_winner"],
        "result_summary": session["result_summary"],
        "rematch_votes": sorted(session["rematch_votes"]),
    }


def _queue_wait_message(position: int, total: int) -> str:
    if total <= 1:
        return "Searching for opponent..."
    if position <= 1:
        return f"Searching for opponent... {total - 1} other operator(s) are in queue."
    return f"Searching for opponent... queue position {position}."


def _idle_matchmaking_payload(message: str) -> dict[str, Any]:
    return {
        "type": "queue_state",
        "status": "idle",
        "position": None,
        "queued_players": len(matchmaking_queue),
        "message": message,
    }


def _queue_state_payload_locked(entry: dict[str, Any], message: str | None = None) -> dict[str, Any]:
    position = None
    for index, queued_entry in enumerate(matchmaking_queue, start=1):
        if queued_entry["client_id"] == entry["client_id"]:
            position = index
            break

    total = len(matchmaking_queue)
    return {
        "type": "queue_state",
        "status": "searching" if position is not None else "idle",
        "position": position,
        "queued_players": total,
        "message": message or (_queue_wait_message(position or 0, total) if position is not None else "Matchmaking is idle."),
    }


def _queue_updates_locked(message_overrides: dict[str, str] | None = None) -> list[tuple[WebSocket, dict[str, Any]]]:
    overrides = message_overrides or {}
    updates: list[tuple[WebSocket, dict[str, Any]]] = []
    for entry in matchmaking_queue:
        updates.append(
            (
                entry["websocket"],
                _queue_state_payload_locked(entry, message=overrides.get(entry["client_id"])),
            )
        )
    return updates


def _mark_matchmaking_action_locked(client_id: str, now: float) -> bool:
    last_action = matchmaking_last_action.get(client_id, 0.0)
    if now - last_action < MATCHMAKING_ACTION_COOLDOWN:
        return False
    matchmaking_last_action[client_id] = now
    return True


def _remove_matchmaking_entry_locked(
    *,
    client_id: str | None = None,
    websocket: WebSocket | None = None,
    clear_assignment: bool = False,
) -> dict[str, Any] | None:
    lookup_client_id = client_id
    if lookup_client_id is None and websocket is not None:
        lookup_client_id = matchmaking_socket_index.get(websocket)
    entry = matchmaking_index.pop(lookup_client_id, None) if lookup_client_id else None

    if entry is None and websocket is not None:
        for queued_entry in matchmaking_queue:
            if queued_entry["websocket"] is websocket:
                entry = queued_entry
                lookup_client_id = queued_entry["client_id"]
                break

    if entry is None and lookup_client_id is None:
        return None

    if lookup_client_id is not None:
        matchmaking_queue[:] = [queued_entry for queued_entry in matchmaking_queue if queued_entry["client_id"] != lookup_client_id]
        if clear_assignment:
            matchmaking_assignments.pop(lookup_client_id, None)

    if entry is not None:
        matchmaking_socket_index.pop(entry["websocket"], None)
    if websocket is not None:
        matchmaking_socket_index.pop(websocket, None)
    return entry


def _cleanup_matchmaking_locked(now: float) -> bool:
    changed = False

    for client_id, assignment in list(matchmaking_assignments.items()):
        if now - float(assignment.get("created_at", 0.0)) > MATCHMAKING_ASSIGNMENT_TTL:
            matchmaking_assignments.pop(client_id, None)

    for client_id, last_action in list(matchmaking_last_action.items()):
        if now - last_action > MATCHMAKING_ASSIGNMENT_TTL:
            matchmaking_last_action.pop(client_id, None)

    stale_entries = [
        entry
        for entry in list(matchmaking_queue)
        if (now - float(entry.get("last_seen", 0.0)) > MATCHMAKING_STALE_TIMEOUT)
        or not _websocket_is_open(entry.get("websocket"))
    ]
    for entry in stale_entries:
        removed = _remove_matchmaking_entry_locked(client_id=entry["client_id"], clear_assignment=False)
        if removed is not None:
            logger.info("Matchmaking stale queue entry removed for %s", removed["player_name"])
            changed = True

    return changed


def _attempt_matchmaking_locked(now: float) -> list[tuple[WebSocket, dict[str, Any]]]:
    dispatches: list[tuple[WebSocket, dict[str, Any]]] = []

    while len(matchmaking_queue) >= SESSION_MAX_HUMANS:
        matched_entries = [matchmaking_queue.pop(0) for _ in range(SESSION_MAX_HUMANS)]
        for entry in matched_entries:
            matchmaking_index.pop(entry["client_id"], None)
            matchmaking_socket_index.pop(entry["websocket"], None)

        session_id = _generate_room_code()
        session = _get_or_create_session(session_id, match_type="public")
        session["game"].log.append("Public matchmaking linked two operators into a live duel.")

        for entry in matched_entries:
            matchmaking_assignments[entry["client_id"]] = {
                "session_id": session_id,
                "created_at": now,
                "player_name": entry["player_name"],
            }

        names = [entry["player_name"] for entry in matched_entries]
        logger.info("Matchmaking paired %s into room %s", " vs ".join(names), session_id)

        for entry in matched_entries:
            opponent_names = [name for name in names if name != entry["player_name"]]
            dispatches.append(
                (
                    entry["websocket"],
                    {
                        "type": "match_found",
                        "status": "matched",
                        "session_id": session_id,
                        "room": _serialize_room(session_id, session),
                        "opponents": opponent_names,
                        "queued_players": len(matchmaking_queue),
                        "message": "Opponent found. Linking you into a live public duel.",
                    },
                )
            )

    return dispatches


async def _dispatch_matchmaking_messages(
    messages: list[tuple[WebSocket, dict[str, Any]]],
    *,
    prune_failures: bool = True,
) -> None:
    if not messages:
        return

    failed_sockets: list[WebSocket] = []
    for websocket, payload in messages:
        try:
            await websocket.send_json(payload)
        except Exception:
            failed_sockets.append(websocket)

    if not prune_failures or not failed_sockets:
        return

    follow_up: list[tuple[WebSocket, dict[str, Any]]] = []
    async with matchmaking_lock:
        changed = False
        for websocket in failed_sockets:
            removed = _remove_matchmaking_entry_locked(websocket=websocket, clear_assignment=False)
            if removed is not None:
                changed = True
        if changed:
            follow_up = _queue_updates_locked()

    if follow_up:
        await _dispatch_matchmaking_messages(follow_up, prune_failures=False)


async def _matchmaking_cleanup_loop() -> None:
    try:
        while True:
            await asyncio.sleep(MATCHMAKING_CLEANUP_INTERVAL)
            now = time.monotonic()
            updates: list[tuple[WebSocket, dict[str, Any]]] = []
            async with matchmaking_lock:
                if _cleanup_matchmaking_locked(now):
                    updates = _queue_updates_locked()
            if updates:
                await _dispatch_matchmaking_messages(updates)
    except asyncio.CancelledError:
        raise


def _compose_state_message(session_id: str, session: dict[str, Any], player_name: str) -> dict[str, Any]:
    state = serialize_state(session["game"])
    state["server_now"] = time.monotonic()
    return {
        "type": "state",
        "state": state,
        "room": _serialize_room(session_id, session),
        "player_name": player_name,
    }


def _drain_public_log(session: dict[str, Any]) -> list[str]:
    cursor = session["log_cursor"]
    lines = session["game"].log[cursor:]
    session["log_cursor"] = len(session["game"].log)
    return lines


def _sanitize_chat_text(text: str) -> str:
    clean = " ".join(text.strip().split())
    return clean[:MAX_CHAT_LENGTH]


def _chat_entry(player_name: str, text: str) -> dict[str, Any]:
    return {
        "player_name": player_name,
        "text": text,
        "timestamp": time.time(),
    }


def _append_chat_message(session: dict[str, Any], player_name: str, text: str) -> dict[str, Any] | None:
    clean = _sanitize_chat_text(text)
    if not clean:
        return None
    entry = _chat_entry(player_name, clean)
    session["chat_history"].append(entry)
    session["chat_history"] = session["chat_history"][-MAX_CHAT_HISTORY:]
    return entry


def _record_match_result(session_id: str, session: dict[str, Any]) -> None:
    game = session["game"]
    if not game.winner or session["result_recorded"]:
        return

    participants = [player.name for player in game.players if player.is_human]
    for name in participants:
        stats = _ensure_score_entry(session, name)
        stats["games"] += 1
        if name == game.winner:
            stats["wins"] += 1
            stats["streak"] += 1
            stats["best_streak"] = max(stats["best_streak"], stats["streak"])
        else:
            stats["streak"] = 0

    losers = [name for name in participants if name != game.winner]
    duration_seconds = max(1, int(time.time() - session["created_at"])) if session["match_started_at"] is None else max(
        1, int(time.monotonic() - session["match_started_at"])
    )

    session["last_winner"] = game.winner
    session["result_summary"] = {
        "winner": game.winner,
        "losers": losers,
        "headline": f"{game.winner} breached the core",
        "detail": "Vote rematch to keep the room score or restart to zero the scoreboard.",
        "duration_seconds": duration_seconds,
        "match_number": session["match_number"],
        "session_id": session_id,
    }
    session["result_recorded"] = True
    session["rematch_votes"].clear()


def _save_match_if_needed(session: dict[str, Any]) -> None:
    game = session["game"]
    if session["saved_match"] or not game.winner or not DB_READY:
        return

    db = SessionLocal()
    try:
        db.add(MatchHistory(winner=game.winner, state_snapshot=serialize_state(game)))
        db.commit()
        session["saved_match"] = True
        print(f"[DB] Saved match winner: {game.winner}")
    except Exception as exc:
        db.rollback()
        print(f"[DB ERROR] Could not save match: {exc}")
    finally:
        db.close()


def _reset_game(session_id: str, session: dict[str, Any], keep_scores: bool, requested_by: str) -> None:
    existing_players = _registered_human_names(session)
    if not keep_scores:
        session["scoreboard"] = {
            player_name: _blank_score_entry()
            for player_name in existing_players
        }

    session["game"] = build_new_game(max_humans=SESSION_MAX_HUMANS, num_ai=SESSION_AI_COUNT)
    session["log_cursor"] = 0
    session["saved_match"] = False
    session["result_recorded"] = False
    session["last_winner"] = None
    session["result_summary"] = None
    session["rematch_votes"].clear()
    session["match_number"] += 1
    session["match_started_at"] = time.monotonic() if len(existing_players) >= SESSION_MAX_HUMANS else None

    for player_name in existing_players:
        add_human_player(session["game"], player_name)

    if keep_scores:
        session["game"].log.append(f"{requested_by} launched a rematch in room {session_id}.")
    else:
        session["game"].log.append(f"{requested_by} restarted room {session_id} and reset the scoreboard.")


def _handle_control_action(session_id: str, session: dict[str, Any], player_name: str, action: str) -> list[str]:
    if action == "rematch":
        if not session["game"].winner:
            return ["The match is still live. Finish the duel before voting rematch."]
        if player_name not in _registered_human_names(session):
            return ["You are not registered for this room."]

        session["rematch_votes"].add(player_name)
        needed_votes = set(_registered_human_names(session))
        if needed_votes and session["rematch_votes"] >= needed_votes:
            _reset_game(session_id, session, keep_scores=True, requested_by=player_name)
            return ["Rematch accepted. New breach window is live."]
        remaining = sorted(needed_votes - session["rematch_votes"])
        if remaining:
            return [f"Rematch vote recorded. Waiting on: {', '.join(remaining)}."]
        return ["Rematch vote recorded."]

    if action == "restart":
        _reset_game(session_id, session, keep_scores=False, requested_by=player_name)
        return ["Room restarted. Scoreboard reset and a fresh match is ready."]

    return ["Unknown control action."]


def _can_process_gameplay_command(session: dict[str, Any], command_name: str) -> tuple[bool, str]:
    if command_name in INFO_ONLY_COMMANDS or command_name == "quit":
        return True, ""

    status = _session_status(session)
    if status == "waiting":
        return False, "Waiting for a second operator. Share the invite link to begin the duel."
    if status == "reconnecting":
        return False, "Opponent offline. The duel is paused until both operators reconnect."
    if status == "finished":
        return False, "Match complete. Use rematch or restart from the room controls."
    return True, ""


async def _send_private_log(websocket: WebSocket, lines: list[str]) -> bool:
    if not lines:
        return True
    try:
        await websocket.send_json({"type": "log", "lines": lines})
        return True
    except Exception:
        return False


async def _broadcast_logs(session: dict[str, Any], lines: list[str]) -> None:
    if not lines:
        return

    stale = []
    for websocket in list(session["clients"].keys()):
        try:
            await websocket.send_json({"type": "log", "lines": lines})
        except Exception:
            stale.append(websocket)

    for websocket in stale:
        session["clients"].pop(websocket, None)


async def _broadcast_state(session_id: str, session: dict[str, Any]) -> None:
    stale = []
    for websocket, player_name in list(session["clients"].items()):
        try:
            await websocket.send_json(_compose_state_message(session_id, session, player_name))
        except Exception:
            stale.append(websocket)

    for websocket in stale:
        session["clients"].pop(websocket, None)


async def _broadcast_chat(session: dict[str, Any], entry: dict[str, Any]) -> None:
    stale = []
    for websocket in list(session["clients"].keys()):
        try:
            await websocket.send_json({"type": "chat", "message": entry})
        except Exception:
            stale.append(websocket)

    for websocket in stale:
        session["clients"].pop(websocket, None)


async def _session_loop(session_id: str) -> None:
    while True:
        await asyncio.sleep(TICK_INTERVAL)
        session = sessions.get(session_id)
        if session is None:
            return

        public_lines: list[str] = []
        state_changed = False
        should_save = False
        now = time.monotonic()

        async with session["lock"]:
            previous_status = _session_status(session)
            if update_temporary_effects(session["game"], now):
                state_changed = True
            if session["game"].winner:
                _record_match_result(session_id, session)
            public_lines = _drain_public_log(session)
            current_status = _session_status(session)
            if current_status != previous_status:
                state_changed = True
            should_save = bool(session["game"].winner and not session["saved_match"])

            if session["clients"]:
                session["idle_since"] = None
            elif session["idle_since"] is None:
                session["idle_since"] = now
            elif now - session["idle_since"] >= IDLE_SESSION_TIMEOUT:
                task = session.get("task")
                if task is not None and task is asyncio.current_task():
                    session["task"] = None
                sessions.pop(session_id, None)
                return

        if should_save:
            _save_match_if_needed(session)
        if public_lines:
            await _broadcast_logs(session, public_lines)
        if public_lines or state_changed:
            await _broadcast_state(session_id, session)


def _command_name(text: str) -> str:
    return (text.strip().split() or [""])[0].lower()


@app.get("/api/matchmaking/status")
async def matchmaking_status() -> dict[str, Any]:
    async with matchmaking_lock:
        _cleanup_matchmaking_locked(time.monotonic())
        return {
            "queued_players": len(matchmaking_queue),
            "pending_assignments": len(matchmaking_assignments),
        }


@app.websocket("/ws-matchmaking")
async def matchmaking_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    client_id: str | None = None

    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                await _dispatch_matchmaking_messages(
                    [(websocket, {"type": "error", "message": "Malformed matchmaking payload."})],
                    prune_failures=False,
                )
                continue

            message_type = str(message.get("type", "")).strip().lower()
            now = time.monotonic()

            if message_type == "queue_join":
                requested_client_id = _normalize_client_id(message.get("client_id"))
                requested_name = normalize_player_name(str(message.get("player_name", "Player")))
                outbound: list[tuple[WebSocket, dict[str, Any]]] = []
                replaced_socket: WebSocket | None = None

                async with matchmaking_lock:
                    _cleanup_matchmaking_locked(now)
                    if not _mark_matchmaking_action_locked(requested_client_id, now):
                        outbound.append(
                            (
                                websocket,
                                {
                                    "type": "error",
                                    "message": "Please wait a moment before searching again.",
                                },
                            )
                        )
                    else:
                        existing_entry = matchmaking_index.get(requested_client_id)
                        if existing_entry is not None and existing_entry["websocket"] is websocket:
                            existing_entry["last_seen"] = now
                            existing_entry["player_name"] = requested_name
                            client_id = requested_client_id
                            outbound.append((websocket, _queue_state_payload_locked(existing_entry)))
                        else:
                            if existing_entry is not None:
                                replaced_socket = existing_entry["websocket"]
                                _remove_matchmaking_entry_locked(client_id=requested_client_id, clear_assignment=False)

                            entry = {
                                "client_id": requested_client_id,
                                "player_name": requested_name,
                                "websocket": websocket,
                                "queued_at": now,
                                "last_seen": now,
                            }
                            matchmaking_queue.append(entry)
                            matchmaking_index[requested_client_id] = entry
                            matchmaking_socket_index[websocket] = requested_client_id
                            client_id = requested_client_id

                            logger.info(
                                "Matchmaking queue join: player=%s client_id=%s queue_size=%s",
                                requested_name,
                                requested_client_id,
                                len(matchmaking_queue),
                            )
                            outbound.extend(_queue_updates_locked())
                            outbound.extend(_attempt_matchmaking_locked(now))

                if replaced_socket is not None:
                    try:
                        await replaced_socket.close()
                    except Exception:
                        pass
                await _dispatch_matchmaking_messages(outbound)
                continue

            if message_type in {"queue_cancel", "cancel"}:
                outbound = []
                async with matchmaking_lock:
                    _cleanup_matchmaking_locked(now)
                    removed = _remove_matchmaking_entry_locked(client_id=client_id, websocket=websocket, clear_assignment=False)
                    if removed is not None:
                        logger.info(
                            "Matchmaking queue cancel: player=%s client_id=%s queue_size=%s",
                            removed["player_name"],
                            removed["client_id"],
                            len(matchmaking_queue),
                        )
                    outbound.append((websocket, _idle_matchmaking_payload("Matchmaking cancelled. You can search again any time.")))
                    outbound.extend(_queue_updates_locked())
                await _dispatch_matchmaking_messages(outbound)
                continue

            if message_type in {"heartbeat", "status"}:
                payload = _idle_matchmaking_payload("Matchmaking is idle.")
                async with matchmaking_lock:
                    _cleanup_matchmaking_locked(now)
                    resolved_client_id = client_id or matchmaking_socket_index.get(websocket)
                    if resolved_client_id is not None and resolved_client_id in matchmaking_index:
                        entry = matchmaking_index[resolved_client_id]
                        entry["last_seen"] = now
                        client_id = resolved_client_id
                        payload = _queue_state_payload_locked(entry)
                await _dispatch_matchmaking_messages([(websocket, payload)], prune_failures=False)
                continue

            await _dispatch_matchmaking_messages(
                [(websocket, {"type": "error", "message": "Unsupported matchmaking message type."})],
                prune_failures=False,
            )
    except WebSocketDisconnect:
        pass
    finally:
        follow_up: list[tuple[WebSocket, dict[str, Any]]] = []
        async with matchmaking_lock:
            removed = _remove_matchmaking_entry_locked(client_id=client_id, websocket=websocket, clear_assignment=False)
            if removed is not None:
                logger.info(
                    "Matchmaking queue disconnect: player=%s client_id=%s queue_size=%s",
                    removed["player_name"],
                    removed["client_id"],
                    len(matchmaking_queue),
                )
                follow_up = _queue_updates_locked()
        if follow_up:
            await _dispatch_matchmaking_messages(follow_up)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    session = _get_or_create_session(session_id)
    player_name = None
    client_id = None

    try:
        raw_message = await websocket.receive_text()
        join_message = json.loads(raw_message)
        if join_message.get("type") != "join":
            await websocket.send_json({"type": "error", "message": "Expected a join message first."})
            await websocket.close()
            return

        requested_name = join_message.get("player_name", "Player")
        client_id = _normalize_client_id(join_message.get("client_id"))
        replaced_socket = None

        async with matchmaking_lock:
            _cleanup_matchmaking_locked(time.monotonic())
            _remove_matchmaking_entry_locked(client_id=client_id, clear_assignment=False)
            assignment = matchmaking_assignments.get(client_id)
            if assignment is not None and assignment.get("session_id") == session_id:
                matchmaking_assignments.pop(client_id, None)

        try:
            async with session["lock"]:
                for existing_socket, existing_name in list(session["clients"].items()):
                    if existing_name.lower() == str(requested_name).strip().lower():
                        replaced_socket = existing_socket
                        session["clients"].pop(existing_socket, None)
                        break

                player, created = add_human_player(session["game"], str(requested_name))
                player_name = player.name
                session["clients"][websocket] = player_name

                if player_name not in session["registered_players"]:
                    session["registered_players"].append(player_name)
                _ensure_score_entry(session, player_name)

                if created:
                    session["game"].log.append(f"{player_name} joined room {session_id}.")
                else:
                    session["game"].log.append(f"{player_name} reconnected to room {session_id}.")

                if len(_registered_human_names(session)) >= SESSION_MAX_HUMANS and session["match_started_at"] is None:
                    session["match_started_at"] = time.monotonic()
                    session["game"].log.append("Two operators linked. The duel is live.")

                public_lines = _drain_public_log(session)
                state_message = _compose_state_message(session_id, session, player_name)
        except ValueError as exc:
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close()
            return

        if replaced_socket is not None:
            try:
                await replaced_socket.close()
            except Exception:
                pass

        await websocket.send_json(
            {
                "type": "welcome",
                "player_name": player_name,
                "session_id": session_id,
                "room": _serialize_room(session_id, session),
            }
        )
        await _send_private_log(
            websocket,
            [
                f"Connected to room '{session_id}' as {player_name}.",
                _room_notice(session),
                "Type 'help' in the terminal to view commands.",
            ],
        )
        await websocket.send_json(
            {
                "type": "chat_history",
                "messages": list(session["chat_history"]),
            }
        )
        if public_lines:
            await _broadcast_logs(session, public_lines)
        await websocket.send_json(state_message)
        await _broadcast_state(session_id, session)

        while True:
            raw_message = await websocket.receive_text()
            message = json.loads(raw_message)
            message_type = message.get("type")

            if message_type == "control":
                async with session["lock"]:
                    response_lines = _handle_control_action(
                        session_id,
                        session,
                        player_name,
                        str(message.get("action", "")).strip().lower(),
                    )
                    if session["game"].winner:
                        _record_match_result(session_id, session)
                    public_lines = _drain_public_log(session)
                if response_lines:
                    still_connected = await _send_private_log(websocket, response_lines)
                    if not still_connected:
                        break
                if public_lines:
                    await _broadcast_logs(session, public_lines)
                await _broadcast_state(session_id, session)
                continue

            if message_type == "chat":
                async with session["lock"]:
                    entry = _append_chat_message(
                        session,
                        player_name,
                        str(message.get("text", "")),
                    )
                if entry is None:
                    still_connected = await _send_private_log(websocket, ["Chat message was empty."])
                    if not still_connected:
                        break
                    continue
                await _broadcast_chat(session, entry)
                continue

            if message_type != "command":
                await _send_private_log(websocket, ["Unsupported message type."])
                continue

            command_text = str(message.get("command", ""))
            command_name = _command_name(command_text)
            if command_name in CONTROL_COMMANDS:
                async with session["lock"]:
                    response_lines = _handle_control_action(session_id, session, player_name, command_name)
                    public_lines = _drain_public_log(session)
                if response_lines:
                    still_connected = await _send_private_log(websocket, response_lines)
                    if not still_connected:
                        break
                if public_lines:
                    await _broadcast_logs(session, public_lines)
                await _broadcast_state(session_id, session)
                continue

            output = StringIO()
            should_save = False

            async with session["lock"]:
                allowed, reason = _can_process_gameplay_command(session, command_name)
                if allowed:
                    handle_command(
                        command_text,
                        session["game"],
                        player_name,
                        output,
                        now=time.monotonic(),
                    )
                else:
                    output.write(reason + "\n")

                if session["game"].winner:
                    _record_match_result(session_id, session)
                public_lines = _drain_public_log(session)
                should_save = bool(session["game"].winner and not session["saved_match"])

            response_lines = [line for line in output.getvalue().splitlines() if line.strip()]
            if response_lines:
                still_connected = await _send_private_log(websocket, response_lines)
                if not still_connected:
                    break
            if should_save:
                _save_match_if_needed(session)
            if public_lines:
                await _broadcast_logs(session, public_lines)
            await _broadcast_state(session_id, session)

    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        await _send_private_log(websocket, ["Malformed JSON message."])
    finally:
        if player_name is None:
            return

        public_lines: list[str] = []
        async with session["lock"]:
            removed = session["clients"].pop(websocket, None)
            if removed is not None:
                session["game"].log.append(f"{player_name} disconnected.")
                public_lines = _drain_public_log(session)

        if public_lines:
            await _broadcast_logs(session, public_lines)
        await _broadcast_state(session_id, session)
