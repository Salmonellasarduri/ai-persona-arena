"""Run a full Ragaman match: INANNA vs Cardman.

Usage:
    cd arena
    python -m examples.run_match
    python -m examples.run_match --theme "animals" --criterion "want-to-become level"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arena.engine import Room
from arena.games.ragaman import Ragaman
from arena.players.inanna import InannaPlayer
from arena.players.cardman import CardmanPlayer
from arena.formatter import format_match_markdown


async def run_match(theme: str, criterion: str, turns: int,
                    personality_dir: str | None = None) -> list[dict]:
    game = Ragaman()
    room = Room(game, {"theme": theme, "criterion": criterion, "turns": turns})

    p1 = InannaPlayer(personality_dir=personality_dir)
    p2 = CardmanPlayer()

    room.join(p1.name)
    room.join(p2.name)

    while not room.is_done():
        obs1 = room.observe(p1.name)
        obs2 = room.observe(p2.name)
        phase = obs1["phase"]

        if phase == "express":
            sys.stdout.write(
                f"  Turn {obs1['turn']}/{obs1['max_turns']} - express ... "
            )
            sys.stdout.flush()
            a1, a2 = await asyncio.gather(p1.express(obs1), p2.express(obs2))
            turn, ph = obs1["turn"], obs1["phase"]
            room.submit(p1.name, a1, turn, ph)
            room.submit(p2.name, a2, turn, ph)
            sys.stdout.write("OK\n")

        elif phase == "guess":
            sys.stdout.write(
                f"  Turn {obs1['turn']}/{obs1['max_turns']} - guess  ... "
            )
            sys.stdout.flush()
            obs1 = room.observe(p1.name)
            obs2 = room.observe(p2.name)
            a1, a2 = await asyncio.gather(p1.guess(obs1), p2.guess(obs2))
            turn, ph = obs1["turn"], obs1["phase"]
            room.submit(p1.name, a1, turn, ph)
            room.submit(p2.name, a2, turn, ph)
            sys.stdout.write("OK\n")

    return room.get_history()


def print_summary(history: list[dict]) -> None:
    """Print ASCII-safe summary to terminal."""
    for h in history:
        cards = h["cards"]
        errs = h["errors"]
        players = list(cards.keys())
        p1, p2 = players
        rg = " RAGAMAN!" if h["is_ragaman"] else ""
        ts = h.get("turn_score", 0)
        print(f"  Turn {h['turn']}: "
              f"{p1}={cards[p1]}(err{errs[p1]}) "
              f"{p2}={cards[p2]}(err{errs[p2]}) "
              f"sum={h['actual_sum']}{rg} +{ts}pts")
    if history:
        pair_score = history[-1].get("pair_score_after", 0)
        max_possible = len(history) * 10
        print(f"\n  Pair score: {pair_score}/{max_possible}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Ragaman match")
    parser.add_argument(
        "--theme", default="drinks",
        help="Game theme (default: drinks)"
    )
    parser.add_argument(
        "--criterion",
        default="want-to-drink-first-thing-in-the-morning level",
        help="Ranking criterion",
    )
    parser.add_argument("--turns", type=int, default=5)
    parser.add_argument("--personality-dir",
                        help="Path to INANNA personality dir (self.md, character_signature.txt)")
    args = parser.parse_args()

    if args.personality_dir:
        print(f"Loading INANNA personality from: {args.personality_dir}")
    print(f"=== Ragaman: INANNA vs CARDMAN ===")
    print(f"Theme: {args.theme} / Criterion: {args.criterion}")
    print(f"Turns: {args.turns}\n")

    history = asyncio.run(run_match(args.theme, args.criterion, args.turns,
                                    args.personality_dir))

    # Save raw JSON
    json_out = Path("match_result.json")
    json_out.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save Markdown
    md = format_match_markdown(
        history, args.theme, args.criterion, ["INANNA", "CARDMAN"]
    )
    md_out = Path("match_result.md")
    md_out.write_text(md, encoding="utf-8")

    # ASCII-safe terminal output
    print(f"\nResults:")
    print_summary(history)
    print(f"\n  JSON: {json_out}")
    print(f"  Markdown: {md_out}")


if __name__ == "__main__":
    main()
