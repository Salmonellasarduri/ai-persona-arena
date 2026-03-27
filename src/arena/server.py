"""MCP Game Server — expose the game engine as MCP tools.

Run:
    python -m arena.server
    python -m arena.server --transport sse --port 8080

External AI agents connect via MCP and play using tools:
    create_room, join_room, get_observation, submit_action, get_history
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

from arena.engine import (
    ActionConflict,
    AlreadySubmitted,
    Room,
    WrongPhase,
    WrongTurn,
)
from arena.games.ragaman import Ragaman

_PROTOCOL_VERSION = "0.2"

# ── Game registry ──

GAMES = {
    "ragaman": {"1.0": Ragaman},
}

# ── Room storage (in-memory) ──

_rooms: dict[str, Room] = {}
_room_configs: dict[str, dict] = {}
_room_locks: dict[str, asyncio.Lock] = {}
_room_last_activity: dict[str, float] = {}
_ROOM_TTL_SECONDS = 600  # 10 minutes

# ── Helpers ──


def _make_success(**payload: Any) -> dict[str, Any]:
    return {"protocol_version": _PROTOCOL_VERSION, **payload}


def _make_error(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _refresh_ttl(room_id: str) -> None:
    _room_last_activity[room_id] = time.monotonic()


def _validate_session(room: Room, player_id: str, session_token: str) -> dict | None:
    """Return error dict if invalid, None if OK."""
    if player_id not in room.players:
        return _make_error("PLAYER_NOT_IN_ROOM", f"{player_id} is not in this room")
    expected = room.session_tokens.get(player_id)
    if expected != session_token:
        return _make_error("INVALID_SESSION", "Session token does not match")
    return None


# ── MCP Server ──

mcp = FastMCP(
    "ai-persona-arena",
    instructions=(
        "AI Persona Arena game server (protocol v0.2). "
        "Create a room, join with your personality, then express and guess "
        "each turn. Both players must submit before the round advances."
    ),
    host="127.0.0.1",
    port=8080,
)


@mcp.tool()
def create_room(
    game_type: str = "ragaman",
    version: str = "1.0",
    theme: str = "drinks",
    criterion: str = "want-to-drink-first-thing-in-the-morning level",
    turns: int = 5,
) -> dict[str, Any]:
    """Create a new game room.

    Args:
        game_type: Game to play (currently: "ragaman")
        version: Game version (currently: "1.0")
        theme: Topic for the game (e.g. "drinks", "animals", "emotions")
        criterion: Ranking axis (e.g. "want-to-drink-first-thing-in-the-morning level")
        turns: Number of turns (default 5)

    Returns:
        room_id to share with the other player.
    """
    _cleanup_expired_rooms()

    versions = GAMES.get(game_type)
    if not versions:
        return _make_error("UNSUPPORTED_MODE", f"Unknown game: {game_type}. Available: {list(GAMES)}")
    game_cls = versions.get(version)
    if not game_cls:
        return _make_error("UNSUPPORTED_MODE", f"Unknown version: {version}. Available: {list(versions)}")

    # Sanitize config
    if not isinstance(turns, int) or turns <= 0 or turns > 99:
        turns = 5

    game = game_cls()
    config = {"game_type": game_type, "version": version,
              "theme": theme, "criterion": criterion, "turns": turns}
    room_id = uuid.uuid4().hex[:8]
    _rooms[room_id] = Room(game, {"theme": theme, "criterion": criterion, "turns": turns})
    _room_configs[room_id] = config
    _room_locks[room_id] = asyncio.Lock()
    _refresh_ttl(room_id)

    return _make_success(room_id=room_id, config=config)


@mcp.tool()
def join_room(
    room_id: str,
    player_name: str = "",
    personality_summary: str = "",
    session_token: str = "",
) -> dict[str, Any]:
    """Join an existing game room.

    Two modes:
    - New join: provide player_name (required).
    - Reconnect: provide session_token (player_name ignored).

    Args:
        room_id: Room ID from create_room
        player_name: Your display name (required for new join)
        personality_summary: Brief description of your AI's personality (optional)
        session_token: For reconnect — reuse a previously issued token
    """
    room = _rooms.get(room_id)
    if not room:
        return _make_error("ROOM_NOT_FOUND", f"Room {room_id} not found")

    # Reconnect mode
    if session_token:
        for pid, tok in room.session_tokens.items():
            if tok == session_token:
                _refresh_ttl(room_id)
                result = room.join(pid)  # idempotent re-join
                return _make_success(
                    player_id=pid,
                    session_token=tok,
                    config=_room_configs.get(room_id, {}),
                    observation=result["observation"],
                )
        return _make_error("INVALID_SESSION", "Session token not found in this room")

    # New join mode
    if not player_name:
        return _make_error("INVALID_ACTION", "player_name is required for new join")

    try:
        result = room.join(player_name)
    except RuntimeError:
        return _make_error("ROOM_FULL", "Room already has 2 players")

    _refresh_ttl(room_id)
    return _make_success(
        player_id=player_name,
        session_token=result["session_token"],
        config=_room_configs.get(room_id, {}),
        observation=result["observation"],
    )


@mcp.tool()
def get_observation(room_id: str, player_id: str) -> dict[str, Any]:
    """Get the current game state visible to you.

    This is the authoritative source of truth. Call after submit_action
    to confirm state advancement.

    Args:
        room_id: Room ID
        player_id: Your player name
    """
    room = _rooms.get(room_id)
    if not room:
        return _make_error("ROOM_NOT_FOUND", f"Room {room_id} not found")

    if player_id not in room.players:
        return _make_error("PLAYER_NOT_IN_ROOM", f"{player_id} is not in this room")

    obs = room.observe(player_id)
    obs["room_status"] = room.room_status
    obs["my_submission_state"] = room.my_submission_state(player_id)
    return _make_success(**obs)


@mcp.tool()
async def submit_action(
    room_id: str,
    player_id: str,
    session_token: str,
    turn: int,
    phase: str,
    action: str,
) -> dict[str, Any]:
    """Submit your action for the current phase.

    In the EXPRESS phase, submit:
        {"expression": "coffee", "spoken_line": "I need this...", "expression_reasoning": "..."}

    In the GUESS phase, submit:
        {"my_guess": 8, "guess_reasoning": "...", "ragaman": false, "ragaman_reasoning": "..."}

    Both players must submit before the round advances.

    Args:
        room_id: Room ID
        player_id: Your player name
        session_token: Session token from join_room
        turn: Current turn number (from get_observation)
        phase: Current phase name (from get_observation)
        action: JSON string with your action
    """
    room = _rooms.get(room_id)
    if not room:
        return _make_error("ROOM_NOT_FOUND", f"Room {room_id} not found")

    # Validate session (bound to player_id)
    err = _validate_session(room, player_id, session_token)
    if err:
        return err

    # Parse action JSON
    try:
        parsed = json.loads(action) if isinstance(action, str) else action
    except json.JSONDecodeError:
        return _make_error("INVALID_ACTION", "Invalid JSON in action")

    lock = _room_locks.get(room_id)
    if not lock:
        return _make_error("ROOM_NOT_FOUND", "Room lock not found")

    _refresh_ttl(room_id)  # refresh on any submit attempt

    async with lock:
        try:
            result = room.submit(player_id, parsed, turn, phase)
        except WrongTurn as e:
            return _make_error("WRONG_TURN", f"Expected turn {e.expected}, got {e.actual}")
        except WrongPhase as e:
            return _make_error("WRONG_PHASE", f"Expected phase '{e.expected}', got '{e.actual}'")
        except AlreadySubmitted as e:
            return _make_success(**e.prior_result)
        except ActionConflict:
            return _make_error("ACTION_CONFLICT", "Different action already submitted for this turn/phase")
        except ValueError as e:
            return _make_error("INVALID_ACTION", str(e))

    return _make_success(**result)


@mcp.tool()
def get_history(room_id: str) -> dict[str, Any]:
    """Get the full history of completed turns.

    Useful for spectating or reviewing a match after it ends.

    Args:
        room_id: Room ID
    """
    room = _rooms.get(room_id)
    if not room:
        return _make_error("ROOM_NOT_FOUND", f"Room {room_id} not found")

    return _make_success(
        config=_room_configs.get(room_id, {}),
        history=room.get_history(),
        phase=room.state.get("phase", ""),
        is_done=room.is_done(),
        pair_score=room.state.get("pair_score", 0),
    )


@mcp.tool()
def list_rooms() -> dict[str, Any]:
    """List all non-terminal game rooms (waiting and active).

    Returns room IDs, game types, and how many players have joined.
    """
    _cleanup_expired_rooms()

    result = []
    for rid, room in _rooms.items():
        if room.is_done():
            continue
        result.append({
            "room_id": rid,
            "config": _room_configs.get(rid, {}),
            "players": room.players,
            "phase": room.state.get("phase", ""),
            "is_done": False,
        })
    return _make_success(rooms=result)


@mcp.tool()
def delete_room(room_id: str, session_token: str = "") -> dict[str, Any]:
    """Delete a game room and free its resources.

    Requires a valid session token from any player in the room.

    Args:
        room_id: Room ID to delete
        session_token: Session token from join_room
    """
    room = _rooms.get(room_id)
    if not room:
        return _make_error("ROOM_NOT_FOUND", f"Room {room_id} not found")

    if not session_token or session_token not in room.session_tokens.values():
        return _make_error("INVALID_SESSION", "Valid session token required to delete a room")

    del _rooms[room_id]
    _room_configs.pop(room_id, None)
    _room_locks.pop(room_id, None)
    _room_last_activity.pop(room_id, None)
    return _make_success(deleted=room_id)


def _cleanup_expired_rooms() -> None:
    now = time.monotonic()
    expired = [
        rid for rid, last in _room_last_activity.items()
        if now - last > _ROOM_TTL_SECONDS
    ]
    for rid in expired:
        _rooms.pop(rid, None)
        _room_configs.pop(rid, None)
        _room_locks.pop(rid, None)
        _room_last_activity.pop(rid, None)


# ── Entry point ──

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="AI Persona Arena MCP Server")
    parser.add_argument("--transport", default="stdio",
                        choices=["stdio", "sse", "streamable-http"],
                        help="MCP transport (default: stdio)")
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
