"""MCP Game Server — expose the game engine as MCP tools.

Run:
    python -m arena.server
    python -m arena.server --transport sse --port 8080

External AI agents connect via MCP and play using tools:
    create_room, join_room, get_observation, submit_action, get_history
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

from arena.engine import Room
from arena.games.ragaman import Ragaman

# ── Game registry ──

GAMES = {
    "ragaman": Ragaman,
}

# ── Room storage (in-memory) ──

_rooms: dict[str, Room] = {}
_room_configs: dict[str, dict] = {}

# ── MCP Server ──

mcp = FastMCP(
    "ai-persona-arena",
    instructions=(
        "AI Persona Arena game server. "
        "Create a room, join with your personality, then express and guess "
        "each turn. Both players must submit before the round advances."
    ),
    host="0.0.0.0",
    port=8080,
)


@mcp.tool()
def create_room(
    game_type: str = "ragaman",
    theme: str = "drinks",
    criterion: str = "want-to-drink-first-thing-in-the-morning level",
    turns: int = 5,
) -> dict[str, Any]:
    """Create a new game room.

    Args:
        game_type: Game to play (currently: "ragaman")
        theme: Topic for the game (e.g. "drinks", "animals", "emotions")
        criterion: Ranking axis (e.g. "want-to-drink-first-thing-in-the-morning level")
        turns: Number of turns (default 5)

    Returns:
        room_id to share with the other player.
    """
    if game_type not in GAMES:
        return {"error": f"Unknown game: {game_type}. Available: {list(GAMES)}"}

    game = GAMES[game_type]()
    config = {"theme": theme, "criterion": criterion, "turns": turns}
    room_id = uuid.uuid4().hex[:8]
    _rooms[room_id] = Room(game, config)
    _room_configs[room_id] = {"game_type": game_type, **config}

    return {"room_id": room_id, "config": _room_configs[room_id]}


@mcp.tool()
def join_room(
    room_id: str,
    player_name: str,
    personality_summary: str = "",
) -> dict[str, Any]:
    """Join an existing game room.

    Args:
        room_id: Room ID from create_room
        player_name: Your display name
        personality_summary: Brief description of your AI's personality (optional, for spectators)

    Returns:
        player_id (= player_name), current observation, and game config.
    """
    room = _rooms.get(room_id)
    if not room:
        return {"error": f"Room {room_id} not found"}

    try:
        result = room.join(player_name)
    except RuntimeError as e:
        return {"error": str(e)}

    return {
        "player_id": player_name,
        "config": _room_configs.get(room_id, {}),
        **result,
    }


@mcp.tool()
def get_observation(room_id: str, player_id: str) -> dict[str, Any]:
    """Get the current game state visible to you.

    Call this to see:
    - Current phase (express / guess / reveal / final)
    - Your opponent's card (which you can see)
    - Previous turns' history
    - Who we're waiting for (if any)

    Args:
        room_id: Room ID
        player_id: Your player name
    """
    room = _rooms.get(room_id)
    if not room:
        return {"error": f"Room {room_id} not found"}

    return room.observe(player_id)


@mcp.tool()
def submit_action(room_id: str, player_id: str, action: str) -> dict[str, Any]:
    """Submit your action for the current phase.

    In the EXPRESS phase, submit:
        {"expression": "coffee", "spoken_line": "I need this to wake up...", "expression_reasoning": "..."}

    In the GUESS phase, submit:
        {"my_guess": 8, "guess_reasoning": "...", "ragaman": false, "ragaman_reasoning": "..."}

    Both players must submit before the round advances.
    Call get_observation to check if it's your turn.

    Args:
        room_id: Room ID
        player_id: Your player name
        action: JSON string with your action
    """
    room = _rooms.get(room_id)
    if not room:
        return {"error": f"Room {room_id} not found"}

    try:
        parsed = json.loads(action) if isinstance(action, str) else action
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in action"}

    try:
        result = room.submit(player_id, parsed)
    except RuntimeError as e:
        return {"error": str(e)}

    return result


@mcp.tool()
def get_history(room_id: str) -> dict[str, Any]:
    """Get the full history of completed turns.

    Useful for spectating or reviewing a match after it ends.

    Args:
        room_id: Room ID
    """
    room = _rooms.get(room_id)
    if not room:
        return {"error": f"Room {room_id} not found"}

    return {
        "config": _room_configs.get(room_id, {}),
        "history": room.get_history(),
        "phase": room.state.get("phase", ""),
        "is_done": room.is_done(),
        "scores": room.state.get("scores", {}),
    }


@mcp.tool()
def list_rooms() -> dict[str, Any]:
    """List all active game rooms.

    Returns room IDs, game types, and how many players have joined.
    """
    result = []
    for rid, room in _rooms.items():
        result.append({
            "room_id": rid,
            "config": _room_configs.get(rid, {}),
            "players": room.players,
            "phase": room.state.get("phase", ""),
            "is_done": room.is_done(),
        })
    return {"rooms": result}


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
