"""Minimal example: create your own AI player in ~20 lines.

Usage:
    cd arena
    python -m examples.simple_player

This runs YOUR custom player against the built-in Cardman.
Edit MY_SYSTEM_PROMPT to change the personality.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arena.engine import Room
from arena.games.ragaman import Ragaman
from arena.players.base import LLMPlayer
from arena.players.cardman import CardmanPlayer
from arena.formatter import format_match_markdown

# ━━━ Edit this to create your own AI personality ━━━

MY_SYSTEM_PROMPT = """\
You are a lazy cat named Tama.
You see everything through the lens of napping, sunbeams, and fish.
You speak in short, sleepy sentences.
You judge things by how comfortable or warm they make you feel.
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main() -> None:
    my_player = LLMPlayer(name="TAMA", system_prompt=MY_SYSTEM_PROMPT)
    opponent = CardmanPlayer()

    game = Ragaman()
    room = Room(game, {
        "theme": "places to visit",
        "criterion": "want-to-go-on-a-day-off level",
        "turns": 3,
    })

    room.join(my_player.name)
    room.join(opponent.name)

    while not room.is_done():
        obs_me = room.observe(my_player.name)
        obs_opp = room.observe(opponent.name)
        phase = obs_me["phase"]

        if phase == "express":
            print(f"  Turn {obs_me['turn']} - express ...", end=" ", flush=True)
            a_me, a_opp = await asyncio.gather(
                my_player.express(obs_me), opponent.express(obs_opp)
            )
            room.submit(my_player.name, a_me)
            room.submit(opponent.name, a_opp)
            print("OK")

        elif phase == "guess":
            print(f"  Turn {obs_me['turn']} - guess  ...", end=" ", flush=True)
            obs_me = room.observe(my_player.name)
            obs_opp = room.observe(opponent.name)
            a_me, a_opp = await asyncio.gather(
                my_player.guess(obs_me), opponent.guess(obs_opp)
            )
            room.submit(my_player.name, a_me)
            room.submit(opponent.name, a_opp)
            print("OK")

    history = room.get_history()

    # Save results
    md = format_match_markdown(
        history, "places to visit", "want-to-go-on-a-day-off level",
        [my_player.name, opponent.name],
    )
    Path("match_result.md").write_text(md, encoding="utf-8")
    Path("match_result.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Terminal summary
    for h in history:
        cards = h["cards"]
        errs = h["errors"]
        players = list(cards.keys())
        print(f"  Turn {h['turn']}: "
              + " / ".join(f"{p}={cards[p]}(err{errs[p]})" for p in players))
    if history:
        final = history[-1]["scores_after"]
        winner = max(final, key=final.get)
        print(f"\n  {final} -> {winner} wins!")
    print(f"\n  Saved: match_result.md / match_result.json")


if __name__ == "__main__":
    print("=== Custom player demo: TAMA vs CARDMAN ===\n")
    asyncio.run(main())
