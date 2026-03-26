"""Core game engine — state machine with simultaneous-commit support."""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import Any


class Game(ABC):
    """Base class for game definitions.

    Subclasses implement the rules; the Room handles turn flow.
    """

    @abstractmethod
    def setup(self, config: dict) -> dict:
        """Return the initial game state dict."""

    @abstractmethod
    def get_observation(self, state: dict, player_id: str) -> dict:
        """Return what *player_id* can see right now."""

    def on_all_joined(self, state: dict, players: list[str]) -> dict:
        """Called when all players have joined. Override to deal cards etc."""
        return state

    @abstractmethod
    def apply_actions(self, state: dict, actions: dict[str, Any]) -> dict:
        """Both players committed — advance state and return it."""

    @abstractmethod
    def is_terminal(self, state: dict) -> bool:
        """True when the game is over."""


class Room:
    """Manages one game session between two players.

    Handles the simultaneous-commit pattern:
    both players submit before anyone sees the other's action.
    """

    def __init__(self, game: Game, config: dict) -> None:
        self.game = game
        self.state = game.setup(config)
        self._pending: dict[str, Any] = {}
        self.players: list[str] = []
        self.log: list[dict] = []

    # -- public API --

    def join(self, player_id: str) -> dict:
        if player_id in self.players:
            return {"ok": True, "observation": self.observe(player_id)}
        if len(self.players) >= 2:
            raise RuntimeError("Room full")
        self.players.append(player_id)
        if len(self.players) == 2:
            self.state = self.game.on_all_joined(self.state, self.players)
        return {"ok": True, "observation": self.observe(player_id)}

    def observe(self, player_id: str) -> dict:
        obs = self.game.get_observation(self.state, player_id)
        obs["waiting_for"] = self._waiting_for()
        return obs

    def submit(self, player_id: str, action: Any) -> dict:
        phase = self.state.get("phase", "")
        if player_id in self._pending:
            raise RuntimeError(f"{player_id} already submitted for {phase}")
        self._pending[player_id] = action
        self._log_action(player_id, phase, action)

        if self._all_committed():
            actions = dict(self._pending)
            self._pending.clear()
            self.state = self.game.apply_actions(
                copy.deepcopy(self.state), actions
            )
        return {"accepted": True, "phase": self.state.get("phase", "")}

    def is_done(self) -> bool:
        return self.game.is_terminal(self.state)

    def get_history(self) -> list[dict]:
        return self.state.get("history", [])

    # -- internals --

    def _all_committed(self) -> bool:
        return set(self._pending.keys()) == set(self.players)

    def _waiting_for(self) -> list[str]:
        return [p for p in self.players if p not in self._pending]

    def _log_action(self, player_id: str, phase: str, action: Any) -> None:
        self.log.append({"player": player_id, "phase": phase, "action": action})
