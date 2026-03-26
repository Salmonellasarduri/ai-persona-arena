"""Ragaman — the value-reading game.

Rules (3 lines):
1. A theme + criterion is announced (e.g. "drinks / want-to-drink-first-thing")
2. Each AI *expresses* the opponent's hidden number in their own words,
   then *guesses* their own number from the opponent's expression.
3. Your personality leaks through your expression. Precision wins.

If both cards sum to 14 and a player calls "Ragaman!", they score a bonus.
"""

from __future__ import annotations

import random
from typing import Any

from arena.engine import Game


class Ragaman(Game):
    """5-turn value-reading game for 2 players."""

    # -- Game interface --

    def setup(self, config: dict) -> dict:
        return {
            "phase": "waiting",
            "turn": 0,
            "max_turns": config.get("turns", 5),
            "theme": config["theme"],
            "criterion": config["criterion"],
            "players": [],
            "cards": {},            # {player_id: int}
            "expressions": {},      # {player_id: {expression, spoken_line, ...}}
            "guesses": {},          # {player_id: {my_guess, reasoning, ragaman, ...}}
            "history": [],
            "scores": {},
        }

    def on_all_joined(self, state: dict, players: list[str]) -> dict:
        state["players"] = list(players)
        state["scores"] = {p: 0 for p in players}
        return self._deal(state)

    def get_observation(self, state: dict, player_id: str) -> dict:
        if state["phase"] == "waiting":
            return {"phase": "waiting", "theme": state["theme"],
                    "criterion": state["criterion"]}
        opp = self._opponent(state, player_id)
        obs: dict[str, Any] = {
            "phase": state["phase"],
            "turn": state["turn"],
            "max_turns": state["max_turns"],
            "theme": state["theme"],
            "criterion": state["criterion"],
            "history": state["history"],
        }

        if state["phase"] in ("express", "guess", "reveal"):
            obs["opponent_card"] = state["cards"].get(opp)

        if state["phase"] == "guess":
            # After both expressed: show all expressions
            obs["expressions"] = dict(state["expressions"])

        if state["phase"] == "reveal":
            obs["expressions"] = dict(state["expressions"])
            obs["guesses"] = dict(state["guesses"])
            obs["cards"] = dict(state["cards"])

        if state["phase"] == "final":
            obs["scores"] = dict(state["scores"])

        return obs

    def apply_actions(self, state: dict, actions: dict[str, Any]) -> dict:
        phase = state["phase"]

        if phase == "express":
            state["expressions"] = dict(actions)
            state["phase"] = "guess"

        elif phase == "guess":
            state["guesses"] = dict(actions)
            state = self._resolve_turn(state)

        return state

    def is_terminal(self, state: dict) -> bool:
        return state["phase"] == "final"

    # -- internals --

    def _deal(self, state: dict) -> dict:
        state["turn"] += 1
        p1, p2 = state["players"]
        state["cards"] = {
            p1: random.randint(1, 13),
            p2: random.randint(1, 13),
        }
        state["expressions"] = {}
        state["guesses"] = {}
        state["phase"] = "express"
        return state

    def _resolve_turn(self, state: dict) -> dict:
        p1, p2 = state["players"]
        c1, c2 = state["cards"][p1], state["cards"][p2]
        actual_sum = c1 + c2
        is_ragaman = actual_sum == 14

        g1 = state["guesses"][p1]
        g2 = state["guesses"][p2]

        # Scoring
        err1 = abs(g1.get("my_guess", 0) - c1)
        err2 = abs(g2.get("my_guess", 0) - c2)
        state["scores"][p1] += max(0, 5 - err1)
        state["scores"][p2] += max(0, 5 - err2)

        # Ragaman bonus
        called1 = g1.get("ragaman", False)
        called2 = g2.get("ragaman", False)
        if is_ragaman:
            if called1:
                state["scores"][p1] += 3
            if called2:
                state["scores"][p2] += 3
        else:
            if called1:
                state["scores"][p1] -= 2
            if called2:
                state["scores"][p2] -= 2

        record = {
            "turn": state["turn"],
            "cards": dict(state["cards"]),
            "expressions": dict(state["expressions"]),
            "guesses": dict(state["guesses"]),
            "actual_sum": actual_sum,
            "is_ragaman": is_ragaman,
            "errors": {p1: err1, p2: err2},
            "scores_after": dict(state["scores"]),
        }
        state["history"].append(record)

        if state["turn"] >= state["max_turns"]:
            state["phase"] = "final"
        else:
            state = self._deal(state)

        return state

    def _opponent(self, state: dict, player_id: str) -> str:
        players = state["players"]
        return players[1] if player_id == players[0] else players[0]
