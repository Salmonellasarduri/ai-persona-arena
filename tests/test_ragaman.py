"""Unit tests for Ragaman game engine (no LLM calls)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arena.engine import Room
from arena.games.ragaman import Ragaman


def make_room(turns: int = 2) -> Room:
    game = Ragaman()
    room = Room(game, {"theme": "test", "criterion": "test-level", "turns": turns})
    room.join("alice")
    room.join("bob")
    return room


class TestRoomSetup:
    def test_initial_phase_is_express(self):
        room = make_room()
        obs = room.observe("alice")
        assert obs["phase"] == "express"

    def test_both_players_see_opponent_card(self):
        room = make_room()
        obs_a = room.observe("alice")
        obs_b = room.observe("bob")
        # alice sees bob's card, bob sees alice's card
        assert "opponent_card" in obs_a
        assert "opponent_card" in obs_b
        assert 1 <= obs_a["opponent_card"] <= 13
        assert 1 <= obs_b["opponent_card"] <= 13

    def test_room_full_raises(self):
        room = make_room()
        try:
            room.join("eve")
            assert False, "Should have raised"
        except RuntimeError:
            pass


class TestSimultaneousCommit:
    def test_first_submit_does_not_advance(self):
        room = make_room()
        room.submit("alice", {"expression": "tea", "spoken_line": "tea!"})
        # Phase should still be express (waiting for bob)
        obs = room.observe("alice")
        assert obs["phase"] == "express"

    def test_both_submit_advances_to_guess(self):
        room = make_room()
        room.submit("alice", {"expression": "tea", "spoken_line": "tea!"})
        room.submit("bob", {"expression": "coffee", "spoken_line": "coffee!"})
        obs = room.observe("alice")
        assert obs["phase"] == "guess"

    def test_guess_phase_shows_expressions(self):
        room = make_room()
        room.submit("alice", {"expression": "tea", "spoken_line": "..."})
        room.submit("bob", {"expression": "coffee", "spoken_line": "..."})
        obs = room.observe("alice")
        assert "expressions" in obs
        assert obs["expressions"]["alice"]["expression"] == "tea"
        assert obs["expressions"]["bob"]["expression"] == "coffee"

    def test_double_submit_raises(self):
        room = make_room()
        room.submit("alice", {"expression": "tea"})
        try:
            room.submit("alice", {"expression": "tea again"})
            assert False, "Should have raised"
        except RuntimeError:
            pass


class TestScoring:
    def _play_turn(self, room: Room, guess_a: int, guess_b: int,
                   ragaman_a: bool = False, ragaman_b: bool = False) -> None:
        # Express phase
        room.submit("alice", {"expression": "x", "spoken_line": "..."})
        room.submit("bob", {"expression": "y", "spoken_line": "..."})
        # Guess phase
        room.submit("alice", {"my_guess": guess_a, "ragaman": ragaman_a})
        room.submit("bob", {"my_guess": guess_b, "ragaman": ragaman_b})

    def test_perfect_guess_scores_10_pair(self):
        room = make_room(turns=1)
        cards = room.state["cards"]
        alice_card = cards["alice"]
        bob_card = cards["bob"]
        self._play_turn(room, alice_card, bob_card)
        history = room.get_history()
        assert history[0]["errors"]["alice"] == 0
        assert history[0]["errors"]["bob"] == 0
        # Pair score: 5 + 5 = 10
        assert history[0]["turn_score"] == 10
        assert history[0]["pair_score_after"] == 10

    def test_ragaman_bonus_on_14(self):
        room = make_room(turns=1)
        room.state["cards"] = {"alice": 6, "bob": 8}
        self._play_turn(room, 6, 8, ragaman_a=True, ragaman_b=False)
        history = room.get_history()
        # Pair: 5+5 (perfect) + 2 (alice ragaman) = 12
        assert history[0]["turn_score"] == 12

    def test_ragaman_penalty_on_wrong(self):
        room = make_room(turns=1)
        room.state["cards"] = {"alice": 5, "bob": 5}
        self._play_turn(room, 5, 5, ragaman_a=True, ragaman_b=False)
        history = room.get_history()
        # Pair: 5+5 (perfect) - 1 (wrong ragaman) = 9
        assert history[0]["turn_score"] == 9

    def test_game_ends_after_max_turns(self):
        room = make_room(turns=2)
        self._play_turn(room, 7, 7)
        assert not room.is_done()
        self._play_turn(room, 7, 7)
        assert room.is_done()
        assert room.state["phase"] == "final"

    def test_history_accumulates(self):
        room = make_room(turns=2)
        self._play_turn(room, 7, 7)
        self._play_turn(room, 7, 7)
        history = room.get_history()
        assert len(history) == 2
        assert history[0]["turn"] == 1
        assert history[1]["turn"] == 2


class TestObservationHiding:
    def test_express_phase_hides_expressions(self):
        room = make_room()
        obs = room.observe("alice")
        assert "expressions" not in obs

    def test_express_phase_hides_own_card(self):
        room = make_room()
        obs = room.observe("alice")
        # Should NOT contain own card directly
        # (opponent_card is the OTHER player's card, which alice CAN see)
        assert "cards" not in obs
