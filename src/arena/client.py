"""Arena Client SDK — play matches without knowing engine internals.

5-minute onboarding:

    from arena.client import play_match

    def my_express(obs):
        card = obs["opponent_card"]
        return {
            "expression": "coffee",
            "spoken_line": "Warm and comforting.",
            "expression_reasoning": f"Card {card} feels like a cozy drink",
        }

    def my_guess(obs):
        return {
            "my_guess": 7,
            "guess_reasoning": "Their expression suggests medium-high",
            "ragaman": False,
            "ragaman_reasoning": "Unlikely to sum to 14",
        }

    history = play_match(
        player_name="MyCoolBot",
        express_fn=my_express,
        guess_fn=my_guess,
        theme="drinks",
        criterion="want-to-drink-first-thing-in-the-morning level",
    )

    for turn in history:
        print(f"Turn {turn['turn']}: score {turn['turn_score']}")
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable

from arena.engine import Room
from arena.games.ragaman import Ragaman
from arena.players.base import LLMPlayer
from arena.players.cardman import CardmanPlayer
from arena.formatter import format_match_markdown


def play_match(
    player_name: str,
    express_fn: Callable[[dict], dict] | None = None,
    guess_fn: Callable[[dict], dict] | None = None,
    system_prompt: str | None = None,
    opponent: str = "cardman",
    theme: str = "drinks",
    criterion: str = "want-to-drink-first-thing-in-the-morning level",
    turns: int = 5,
    save_results: bool = True,
) -> list[dict]:
    """Play a full Ragaman match. Returns match history.

    Provide EITHER callback functions (express_fn + guess_fn) for manual
    control, OR a system_prompt to let an LLM play with your personality.

    Args:
        player_name: Your bot's display name.
        express_fn: Called with observation dict, returns express action dict.
        guess_fn: Called with observation dict, returns guess action dict.
        system_prompt: If set, uses LLM (Claude) to play with this personality.
            Ignored if express_fn/guess_fn are provided.
        opponent: "cardman" (default) or a system prompt string for LLM opponent.
        theme: Game theme.
        criterion: Ranking criterion.
        turns: Number of turns.
        save_results: Save match_result.json and match_result.md (default True).

    Returns:
        List of turn records (same as Room.get_history()).
    """
    return asyncio.run(_play_match_async(
        player_name, express_fn, guess_fn, system_prompt,
        opponent, theme, criterion, turns, save_results,
    ))


async def _play_match_async(
    player_name: str,
    express_fn: Callable[[dict], dict] | None,
    guess_fn: Callable[[dict], dict] | None,
    system_prompt: str | None,
    opponent: str,
    theme: str,
    criterion: str,
    turns: int,
    save_results: bool,
) -> list[dict]:
    game = Ragaman()
    room = Room(game, {"theme": theme, "criterion": criterion, "turns": turns})

    # Set up players
    if express_fn and guess_fn:
        p1 = _CallbackPlayer(player_name, express_fn, guess_fn)
    elif system_prompt:
        p1 = LLMPlayer(name=player_name, system_prompt=system_prompt)
    else:
        raise ValueError("Provide either (express_fn + guess_fn) or system_prompt")

    if opponent == "cardman":
        p2 = CardmanPlayer()
    else:
        p2 = LLMPlayer(name="Opponent", system_prompt=opponent)

    room.join(p1.name)
    room.join(p2.name)

    while not room.is_done():
        obs1 = room.observe(p1.name)
        obs2 = room.observe(p2.name)
        phase = obs1["phase"]
        turn = obs1["turn"]

        if phase == "express":
            a1, a2 = await asyncio.gather(
                _get_action(p1, "express", obs1),
                _get_action(p2, "express", obs2),
            )
            room.submit(p1.name, a1, turn, phase)
            room.submit(p2.name, a2, turn, phase)

        elif phase == "guess":
            obs1 = room.observe(p1.name)
            obs2 = room.observe(p2.name)
            a1, a2 = await asyncio.gather(
                _get_action(p1, "guess", obs1),
                _get_action(p2, "guess", obs2),
            )
            room.submit(p1.name, a1, turn, phase)
            room.submit(p2.name, a2, turn, phase)

    history = room.get_history()

    if save_results:
        Path("match_result.json").write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        md = format_match_markdown(history, theme, criterion, [p1.name, p2.name])
        Path("match_result.md").write_text(md, encoding="utf-8")

    return history


class _CallbackPlayer:
    """Wraps user-provided callback functions as a player."""

    def __init__(self, name: str,
                 express_fn: Callable[[dict], dict],
                 guess_fn: Callable[[dict], dict]):
        self.name = name
        self._express_fn = express_fn
        self._guess_fn = guess_fn

    async def express(self, observation: dict) -> dict:
        return self._express_fn(observation)

    async def guess(self, observation: dict) -> dict:
        return self._guess_fn(observation)


async def _get_action(player: Any, phase: str, obs: dict) -> dict:
    if phase == "express":
        return await player.express(obs)
    return await player.guess(obs)
