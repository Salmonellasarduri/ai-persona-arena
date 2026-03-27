"""Demo: play Ragaman via MCP protocol (v0.2).

Starts the MCP server as a subprocess and connects as a client.
Two simulated players take turns via MCP tool calls.

Usage:
    cd ai-persona-arena
    python -m examples.mcp_client_demo
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client

SERVER_SCRIPT = str(Path(__file__).parent.parent / "src" / "arena" / "server.py")
SRC_DIR = str(Path(__file__).parent.parent / "src")


async def call_tool(session: ClientSession, name: str, args: dict) -> dict:
    result = await session.call_tool(name, arguments=args)
    text = "\n".join(item.text for item in result.content if hasattr(item, "text"))
    return json.loads(text)


async def main() -> None:
    import os
    env = {**os.environ, "PYTHONPATH": SRC_DIR}
    params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT, "--transport", "stdio"],
        env=env,
    )

    print("Connecting to MCP server...")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List tools
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools.tools]}")

            # Create room
            room = await call_tool(session, "create_room", {
                "game_type": "ragaman",
                "theme": "animals",
                "criterion": "cuteness level",
                "turns": 1,
            })
            room_id = room["room_id"]
            print(f"Room created: {room_id} (protocol v{room['protocol_version']})")

            # Join as two players
            j1 = await call_tool(session, "join_room", {
                "room_id": room_id, "player_name": "Alice",
            })
            token_a = j1["session_token"]

            j2 = await call_tool(session, "join_room", {
                "room_id": room_id, "player_name": "Bob",
            })
            token_b = j2["session_token"]
            print(f"Both players joined. Phase: {j2['observation']['phase']}")

            # Express phase
            obs_a = await call_tool(session, "get_observation", {
                "room_id": room_id, "player_id": "Alice",
            })
            obs_b = await call_tool(session, "get_observation", {
                "room_id": room_id, "player_id": "Bob",
            })
            print(f"Alice sees opponent card: {obs_a.get('opponent_card')}")
            print(f"Bob sees opponent card: {obs_b.get('opponent_card')}")

            turn = obs_a["turn"]

            await call_tool(session, "submit_action", {
                "room_id": room_id, "player_id": "Alice",
                "session_token": token_a,
                "turn": turn, "phase": "express",
                "action": json.dumps({
                    "expression": "hamster",
                    "spoken_line": "So fluffy and small!",
                    "expression_reasoning": "moderately cute",
                }),
            })
            r = await call_tool(session, "submit_action", {
                "room_id": room_id, "player_id": "Bob",
                "session_token": token_b,
                "turn": turn, "phase": "express",
                "action": json.dumps({
                    "expression": "cat",
                    "spoken_line": "Elegant and mysterious.",
                    "expression_reasoning": "quite cute",
                }),
            })
            print(f"Both expressed. Phase: {r['phase']}")

            # Guess phase
            await call_tool(session, "submit_action", {
                "room_id": room_id, "player_id": "Alice",
                "session_token": token_a,
                "turn": turn, "phase": "guess",
                "action": json.dumps({
                    "my_guess": 8,
                    "guess_reasoning": "cat is quite cute",
                    "ragaman": False,
                    "ragaman_reasoning": "not sure",
                }),
            })
            await call_tool(session, "submit_action", {
                "room_id": room_id, "player_id": "Bob",
                "session_token": token_b,
                "turn": turn, "phase": "guess",
                "action": json.dumps({
                    "my_guess": 5,
                    "guess_reasoning": "hamster is moderately cute",
                    "ragaman": False,
                    "ragaman_reasoning": "not sure",
                }),
            })

            # Get results
            history = await call_tool(session, "get_history", {
                "room_id": room_id,
            })
            print(f"\nGame over: {history['is_done']}")
            print(f"Pair score: {history['pair_score']}")
            for h in history["history"]:
                print(f"  Turn {h['turn']}: cards={h['cards']} "
                      f"errors={h['errors']} sum={h['actual_sum']}")

    print("\nMCP demo complete!")


if __name__ == "__main__":
    asyncio.run(main())
