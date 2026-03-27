"""Unit tests for Ragaman game engine (no LLM calls)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arena.engine import (
    ActionConflict,
    AlreadySubmitted,
    Room,
    WrongPhase,
    WrongTurn,
)
from arena.games.ragaman import Ragaman


def make_room(turns: int = 2) -> Room:
    game = Ragaman()
    room = Room(game, {"theme": "test", "criterion": "test-level", "turns": turns})
    room.join("alice")
    room.join("bob")
    return room


def _express(room: Room, player: str, expr: str = "x") -> dict:
    turn = room.state["turn"]
    phase = room.state["phase"]
    return room.submit(player, {"expression": expr, "spoken_line": "..."}, turn, phase)


def _guess(room: Room, player: str, guess: int = 7,
           ragaman: bool = False) -> dict:
    turn = room.state["turn"]
    phase = room.state["phase"]
    return room.submit(player, {"my_guess": guess, "ragaman": ragaman}, turn, phase)


class TestRoomSetup:
    def test_initial_phase_is_express(self):
        room = make_room()
        obs = room.observe("alice")
        assert obs["phase"] == "express"

    def test_both_players_see_opponent_card(self):
        room = make_room()
        obs_a = room.observe("alice")
        obs_b = room.observe("bob")
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
        _express(room, "alice", "tea")
        obs = room.observe("alice")
        assert obs["phase"] == "express"

    def test_both_submit_advances_to_guess(self):
        room = make_room()
        _express(room, "alice", "tea")
        _express(room, "bob", "coffee")
        obs = room.observe("alice")
        assert obs["phase"] == "guess"

    def test_guess_phase_shows_expressions(self):
        room = make_room()
        _express(room, "alice", "tea")
        _express(room, "bob", "coffee")
        obs = room.observe("alice")
        assert "expressions" in obs
        assert obs["expressions"]["alice"]["expression"] == "tea"
        assert obs["expressions"]["bob"]["expression"] == "coffee"

    def test_double_submit_raises_already_submitted(self):
        room = make_room()
        action = {"expression": "tea", "spoken_line": "..."}
        turn = room.state["turn"]
        phase = room.state["phase"]
        room.submit("alice", action, turn, phase)
        try:
            room.submit("alice", action, turn, phase)
            assert False, "Should have raised AlreadySubmitted"
        except AlreadySubmitted as e:
            assert e.prior_result["accepted"] is True


class TestScoring:
    def _play_turn(self, room: Room, guess_a: int, guess_b: int,
                   ragaman_a: bool = False, ragaman_b: bool = False) -> None:
        _express(room, "alice")
        _express(room, "bob")
        _guess(room, "alice", guess_a, ragaman_a)
        _guess(room, "bob", guess_b, ragaman_b)

    def test_perfect_guess_scores_10_pair(self):
        room = make_room(turns=1)
        cards = room.state["cards"]
        self._play_turn(room, cards["alice"], cards["bob"])
        history = room.get_history()
        assert history[0]["errors"]["alice"] == 0
        assert history[0]["errors"]["bob"] == 0
        assert history[0]["turn_score"] == 10
        assert history[0]["pair_score_after"] == 10

    def test_ragaman_bonus_on_14(self):
        room = make_room(turns=1)
        room.state["cards"] = {"alice": 6, "bob": 8}
        self._play_turn(room, 6, 8, ragaman_a=True, ragaman_b=False)
        history = room.get_history()
        assert history[0]["turn_score"] == 12

    def test_ragaman_penalty_on_wrong(self):
        room = make_room(turns=1)
        room.state["cards"] = {"alice": 5, "bob": 5}
        self._play_turn(room, 5, 5, ragaman_a=True, ragaman_b=False)
        history = room.get_history()
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
        assert "cards" not in obs


# ── v0.2 Session Protocol Tests ──

class TestSessionTokens:
    def test_join_returns_session_token(self):
        game = Ragaman()
        room = Room(game, {"theme": "t", "criterion": "c", "turns": 1})
        result = room.join("alice")
        token = result["session_token"]
        assert isinstance(token, str)
        assert len(token) == 32  # uuid4 hex

    def test_rejoin_same_name_returns_same_token(self):
        game = Ragaman()
        room = Room(game, {"theme": "t", "criterion": "c", "turns": 1})
        r1 = room.join("alice")
        r2 = room.join("alice")
        assert r1["session_token"] == r2["session_token"]

    def test_session_tokens_stored(self):
        room = make_room()
        assert "alice" in room.session_tokens
        assert "bob" in room.session_tokens
        assert room.session_tokens["alice"] != room.session_tokens["bob"]


class TestRoomStatus:
    def test_waiting_status(self):
        game = Ragaman()
        room = Room(game, {"theme": "t", "criterion": "c", "turns": 1})
        room.join("alice")
        assert room.room_status == "waiting"

    def test_active_status(self):
        room = make_room()
        assert room.room_status == "active"

    def test_completed_status(self):
        room = make_room(turns=1)
        _express(room, "alice")
        _express(room, "bob")
        _guess(room, "alice")
        _guess(room, "bob")
        assert room.room_status == "completed"

    def test_my_submission_state_pending(self):
        room = make_room()
        assert room.my_submission_state("alice") == "pending"

    def test_my_submission_state_submitted(self):
        room = make_room()
        _express(room, "alice")
        assert room.my_submission_state("alice") == "submitted"

    def test_my_submission_state_non_member(self):
        room = make_room()
        assert room.my_submission_state("eve") is None

    def test_my_submission_state_completed(self):
        room = make_room(turns=1)
        _express(room, "alice")
        _express(room, "bob")
        _guess(room, "alice")
        _guess(room, "bob")
        assert room.my_submission_state("alice") is None


class TestIdempotency:
    def test_same_payload_returns_prior_result(self):
        room = make_room()
        action = {"expression": "tea", "spoken_line": "..."}
        turn = room.state["turn"]
        phase = room.state["phase"]
        first = room.submit("alice", action, turn, phase)
        try:
            room.submit("alice", action, turn, phase)
            assert False, "Should raise AlreadySubmitted"
        except AlreadySubmitted as e:
            assert e.prior_result == first

    def test_different_payload_raises_conflict(self):
        room = make_room()
        turn = room.state["turn"]
        phase = room.state["phase"]
        room.submit("alice", {"expression": "tea", "spoken_line": "..."}, turn, phase)
        try:
            room.submit("alice", {"expression": "coffee", "spoken_line": "..."}, turn, phase)
            assert False, "Should raise ActionConflict"
        except ActionConflict:
            pass

    def test_wrong_turn_raises(self):
        room = make_room()
        phase = room.state["phase"]
        try:
            room.submit("alice", {"expression": "tea", "spoken_line": "..."}, 99, phase)
            assert False, "Should raise WrongTurn"
        except WrongTurn as e:
            assert e.expected == room.state["turn"]
            assert e.actual == 99

    def test_wrong_phase_raises(self):
        room = make_room()
        turn = room.state["turn"]
        try:
            room.submit("alice", {"my_guess": 5}, turn, "guess")
            assert False, "Should raise WrongPhase"
        except WrongPhase as e:
            assert e.expected == "express"
            assert e.actual == "guess"

    def test_validation_order_turn_before_conflict(self):
        """WRONG_TURN should be checked before ACTION_CONFLICT."""
        room = make_room()
        turn = room.state["turn"]
        phase = room.state["phase"]
        room.submit("alice", {"expression": "tea", "spoken_line": "..."}, turn, phase)
        # Wrong turn + different payload → should get WrongTurn, not ActionConflict
        try:
            room.submit("alice", {"expression": "coffee", "spoken_line": "..."}, 99, phase)
            assert False, "Should raise WrongTurn"
        except WrongTurn:
            pass

    def test_submit_after_completion_raises_wrong_phase(self):
        room = make_room(turns=1)
        _express(room, "alice")
        _express(room, "bob")
        _guess(room, "alice")
        _guess(room, "bob")
        assert room.is_done()
        try:
            room.submit("alice", {"expression": "late"}, 1, "express")
            assert False, "Should raise WrongPhase"
        except (WrongTurn, WrongPhase):
            pass  # either is acceptable — turn/phase both differ from final state
