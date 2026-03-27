"""Core game engine — state machine with simultaneous-commit support."""

from __future__ import annotations

import copy
import json
import uuid
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


# ── Engine-level exceptions (server maps these to structured errors) ──

class WrongTurn(Exception):
    def __init__(self, expected: int, actual: int):
        self.expected = expected
        self.actual = actual
        super().__init__(f"Expected turn {expected}, got {actual}")


class WrongPhase(Exception):
    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(f"Expected phase '{expected}', got '{actual}'")


class ActionConflict(Exception):
    pass


class AlreadySubmitted(Exception):
    def __init__(self, prior_result: dict):
        self.prior_result = prior_result
        super().__init__("Already submitted for this turn/phase")


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
        self.session_tokens: dict[str, str] = {}  # {player_id: uuid4}
        self._submitted_actions: dict[tuple, tuple] = {}  # {(pid,turn,phase): (canonical, result)}

    # -- public API --

    @property
    def room_status(self) -> str:
        if len(self.players) < 2:
            return "waiting"
        if self.is_done():
            return "completed"
        return "active"

    def my_submission_state(self, player_id: str) -> str | None:
        """Return 'submitted', 'pending', or None (non-member/completed)."""
        if player_id not in self.players:
            return None
        if self.is_done():
            return None
        if player_id in self._pending:
            return "submitted"
        return "pending"

    def join(self, player_id: str) -> dict:
        if player_id in self.players:
            return {
                "observation": self.observe(player_id),
                "session_token": self.session_tokens[player_id],
            }
        if len(self.players) >= 2:
            raise RuntimeError("Room full")
        token = uuid.uuid4().hex
        self.session_tokens[player_id] = token
        self.players.append(player_id)
        if len(self.players) == 2:
            self.state = self.game.on_all_joined(self.state, self.players)
        return {
            "observation": self.observe(player_id),
            "session_token": token,
        }

    def observe(self, player_id: str) -> dict:
        obs = self.game.get_observation(self.state, player_id)
        obs["waiting_for"] = self._waiting_for()
        return obs

    def submit(self, player_id: str, action: Any,
               turn: int, phase: str) -> dict:
        cur_turn = self.state.get("turn", 0)
        cur_phase = self.state.get("phase", "")

        # 1. Validate turn
        if turn != cur_turn:
            raise WrongTurn(expected=cur_turn, actual=turn)

        # 2. Validate phase
        if phase != cur_phase:
            raise WrongPhase(expected=cur_phase, actual=phase)

        # 3. Idempotency check
        key = (player_id, turn, phase)
        try:
            canonical = json.dumps(action, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Action not JSON-serializable: {exc}") from exc
        if key in self._submitted_actions:
            stored_canonical, stored_result = self._submitted_actions[key]
            if canonical == stored_canonical:
                raise AlreadySubmitted(prior_result=stored_result)
            raise ActionConflict()

        # 4. Normal submit
        self._pending[player_id] = action
        self._log_action(player_id, cur_phase, action)

        result = {"accepted": True, "phase": cur_phase}

        if self._all_committed():
            actions = dict(self._pending)
            self._pending.clear()
            self.state = self.game.apply_actions(
                copy.deepcopy(self.state), actions
            )
            result["phase"] = self.state.get("phase", "")
            # Cleanup old idempotency entries
            self._cleanup_submitted_actions()

        # 5. Store for idempotency
        self._submitted_actions[key] = (canonical, result)

        return result

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

    def _cleanup_submitted_actions(self) -> None:
        """Remove idempotency entries older than previous turn.

        Keeps current turn + previous turn entries for retry safety.
        A network retry after phase advance still gets AlreadySubmitted
        instead of WrongPhase/WrongTurn.
        """
        cur_turn = self.state.get("turn", 0)
        to_remove = [k for k in self._submitted_actions if k[1] < cur_turn - 1]
        for k in to_remove:
            del self._submitted_actions[k]
