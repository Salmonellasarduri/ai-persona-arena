# Arena Session Protocol v0.2

> **Status**: Draft
> **Scope**: Ragaman only · local/private deployment · synchronous polling
> **Breaking changes are expected** until v1.0.

## 1. Overview

This document defines the session-layer contract for the AI Persona Arena
MCP Server. All clients — CLI scripts, MCP tool-use agents, Discord adapters —
MUST follow these rules to interact correctly with the server.

**v0.2 scope boundaries (what is NOT included):**

- Server-Sent Events or push notifications
- Public/multi-tenant authentication
- Spectator mode
- Multi-game negotiation beyond `create_room` validation
- Admin or moderation actions
- Rate limiting (delegated to transport layer)

---

## 2. Protocol Conventions

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are used as
described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

- **Serialization**: JSON. All request parameters and response payloads are
  JSON values. Most are objects, but `submit_action.action` is a JSON string
  encoding an inner object (for MCP transport compatibility with v0.1).
- **Field naming**: `snake_case`.
- **Forward compatibility**: Clients MUST ignore unknown fields in responses.
  Servers MUST ignore unknown fields in action payloads.
- **Integers**: Transmitted as JSON numbers, never strings.
- **Strings**: UTF-8 encoded.

---

## 3. Response Envelope

### 3.1 Success

Every successful response includes `protocol_version`:

```json
{
  "protocol_version": "0.2",
  ...payload fields...
}
```

### 3.2 Error

```json
{
  "error": {
    "code": "ROOM_NOT_FOUND",
    "message": "Room abc12345 not found",
    "detail": "optional additional context"
  }
}
```

Error responses do NOT include `protocol_version`.

---

## 4. Room State Machine

### 4.1 States

```
                    ┌──────────────────────────────┐
                    │                              │
  create_room ──► WAITING ──► ACTIVE ──► COMPLETED │
                    │            │                  │
                    └──► ABANDONED ◄──┘              │
                                                    │
                    (TTL expiry from any non-terminal state)
```

| State | Description |
|-------|-------------|
| `waiting` | Room created, waiting for 2 players to join |
| `active` | Both players joined. Game in progress |
| `completed` | Game reached terminal phase (`final`). Read-only |
| `abandoned` | Room expired via TTL. Physically deleted from server memory |

`completed` and `abandoned` are terminal — no further transitions.

**`abandoned` is not observable** — when a room expires, it is physically
deleted. Clients will receive `ROOM_NOT_FOUND` (if never aware of the room)
or `ROOM_EXPIRED` (if the server detects TTL expiry at lookup time before
deletion). `room_status` values visible to clients are: `waiting`, `active`,
`completed` only.

### 4.2 Active Sub-States (Ragaman)

While `active`, the game phase cycles:

```
express ──(both submit)──► guess ──(both submit)──► [resolve]
                                                       │
                                     turn < max_turns? ─┤
                                     YES: ──► express (next turn)
                                     NO:  ──► final (→ COMPLETED)
```

Phase completion trigger: ALL players MUST submit before `apply_actions()` runs.
A single submission never advances the phase.

**Note:** v0.1 code contains a `reveal` observation branch (`get_observation`
checks for `phase == "reveal"`), but this phase is never entered —
`_resolve_turn` transitions directly from `guess` to `express` or `final`.
v0.2 does not include a `reveal` phase. Turn resolution data is available
via `history` after the guess phase resolves.

### 4.3 State Transitions

| From | To | Trigger |
|------|----|---------|
| `waiting` | `active` (express) | Second player calls `join_room` |
| `active` (express) | `active` (guess) | Both players submit express actions |
| `active` (guess) | `active` (express) | Both submit guess actions AND turn < max_turns |
| `active` (guess) | `completed` (final) | Both submit guess actions AND turn >= max_turns |
| `waiting` | `abandoned` | TTL expiry |
| `active` | `abandoned` | TTL expiry |

---

## 5. Session Identity

### 5.1 Session Token

- `session_token`: UUID4 string, issued by `join_room`.
- MUST be included in all mutating operations: `submit_action`, `delete_room`.
- NOT required for read operations: `get_observation`, `get_history`, `list_rooms`.

### 5.2 Player Identity

- `player_id` = `player_name` (the display name provided at join time).
- `player_id` is unique within a room (enforced by the server on join).
- `player_id` is a display identifier, not an authentication credential.
- `session_token` is the authentication credential.
- Re-joining with the same `player_name` and no token is equivalent to
  reconnect — the server returns the existing session (no new token).
  Only one `session_token` is active per `player_id` per room at a time.

### 5.3 Reconnect

A client that loses connection MAY reconnect by calling:

```
join_room(room_id, session_token=<previously issued token>)
```

- Reconnect MUST be side-effect free (no duplicate join).
- Server returns current `observation` as if freshly joined.
- Pending actions (submitted but not yet resolved) are preserved.

### 5.4 Token Lifecycle

| Event | Token State |
|-------|-------------|
| `join_room` success | Issued (active) |
| Any mutating op with valid token | Active |
| Room reaches `completed` | Read-only (submit rejected, observe OK) |
| Room TTL expires / `delete_room` | Invalid (`INVALID_SESSION`) |

### 5.5 Multi-Client

Multiple clients MAY use the same `session_token` concurrently.
At-most-one-action-per-(player, turn, phase) protects against conflicts.

### 5.6 `INVALID_SESSION` Semantics

The server returns `INVALID_SESSION` when the token is:
- Not a valid UUID4
- Not associated with any room
- Associated with a deleted or expired room
- Not matching the room specified in the request

---

## 6. Tool Contracts

### 6.1 `create_room` — CHANGED in v0.2

Creates a new game room.

**Request:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `game_type` | string | no | `"ragaman"` | Game to play |
| `version` | string | no | `"1.0"` | Game version (NEW) |
| `theme` | string | no | `"drinks"` | Topic for the game |
| `criterion` | string | no | `"want-to-drink..."` | Ranking axis |
| `turns` | int | no | `5` | Number of turns |

**Success Response:**

```json
{
  "protocol_version": "0.2",
  "room_id": "a1b2c3d4",
  "config": {
    "game_type": "ragaman",
    "version": "1.0",
    "theme": "drinks",
    "criterion": "want-to-drink-first-thing-in-the-morning level",
    "turns": 5
  }
}
```

**Errors:**

| Code | Condition |
|------|-----------|
| `UNSUPPORTED_MODE` | Unknown `game_type` or `version` |

**Config validation:** The server applies defaults for missing or invalid
config fields. Non-integer `turns`, values ≤ 0, or values > 99 are replaced
with the default (5). Empty `theme`/`criterion` are replaced with defaults.
Type mismatches in MCP tool parameters are handled by the MCP framework.

---

### 6.2 `join_room` — CHANGED in v0.2

Joins an existing room. Issues a session token.

**Request:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `room_id` | string | yes | Room ID from `create_room` |
| `player_name` | string | **see below** | Display name |
| `personality_summary` | string | no | Brief personality description |
| `session_token` | string | no | For reconnect (NEW) |

**Two modes:**
- **New join**: `player_name` is REQUIRED, `session_token` is absent.
- **Reconnect**: `session_token` is REQUIRED, `player_name` is ignored (MAY be omitted).

`player_name` MUST be unique within the room. Two players with the same
name is not allowed.

**Success Response:**

```json
{
  "protocol_version": "0.2",
  "player_id": "INANNA",
  "session_token": "550e8400-e29b-41d4-a716-446655440000",
  "config": { ... },
  "observation": { ... }
}
```

On reconnect (same `session_token`), the response is identical.
On re-join (same `player_name`, no token), the existing `session_token` is
returned (not a new one).

When `session_token` is provided, `player_name` is ignored — the server
uses the player identity associated with the token.

**Errors:**

| Code | Condition |
|------|-----------|
| `ROOM_NOT_FOUND` | `room_id` does not exist |
| `ROOM_FULL` | Already 2 players and caller is not one of them |
| `ROOM_EXPIRED` | Room was cleaned up by TTL |
| `INVALID_SESSION` | `session_token` provided but invalid |

---

### 6.3 `get_observation` — CHANGED in v0.2

Returns the authoritative game state visible to the requesting player.

`get_observation` is the **single source of truth**. Clients SHOULD call it
after `submit_action` to confirm state advancement. Submit responses are
advisory only.

**Request:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `room_id` | string | yes | Room ID |
| `player_id` | string | yes | Your player name |

**Success Response:**

```json
{
  "protocol_version": "0.2",
  "room_status": "active",
  "phase": "express",
  "turn": 1,
  "max_turns": 5,
  "theme": "drinks",
  "criterion": "want-to-drink-first-thing-in-the-morning level",
  "waiting_for": ["CARDMAN"],
  "my_submission_state": "submitted",
  "history": [],
  ...phase-specific fields...
}
```

New fields in v0.2:
- `room_status`: `"waiting"` | `"active"` | `"completed"`
- `my_submission_state`: `"pending"` | `"submitted"` (whether caller has submitted this turn/phase)

**`phase` values:** `"waiting"` | `"express"` | `"guess"` | `"final"`.
When `room_status` is `"waiting"`, `phase` is `"waiting"`.
When `room_status` is `"active"`, `phase` is one of `"express"` or `"guess"`.
When `room_status` is `"completed"`, `phase` is `"final"`.

**v0.2 security note:** `get_observation` does not require `session_token`.
Any client that knows `room_id` and `player_id` can read that player's
observation. This is acceptable for local/private deployments. Public
deployments (v0.3+) SHOULD require `session_token` for observation.

**Errors:**

| Code | Condition |
|------|-----------|
| `ROOM_NOT_FOUND` | `room_id` does not exist |
| `PLAYER_NOT_IN_ROOM` | `player_id` is not a participant in this room |

---

### 6.4 Observation Visibility Matrix (Ragaman)

| Field | waiting | express | guess | final |
|-------|---------|---------|-------|-------|
| `phase` | ✓ | ✓ | ✓ | ✓ |
| `theme` | ✓ | ✓ | ✓ | ✓ |
| `criterion` | ✓ | ✓ | ✓ | ✓ |
| `turn` | — | ✓ | ✓ | ✓ |
| `max_turns` | — | ✓ | ✓ | ✓ |
| `history` | — | ✓ | ✓ | ✓ |
| `opponent_card` | — | ✓ | — | — |
| `expressions` | — | — | ✓ | — |
| `guesses` | — | — | — | — |
| `cards` | — | — | — | — |
| `pair_score` | — | — | — | ✓ |
| `waiting_for` | ✓ | ✓ | ✓ | ✓ |

**Key rules:**
- Your own card is NEVER visible to you during the game.
- `opponent_card` is visible ONLY during the `express` phase.
- `expressions` become visible in the `guess` phase (after both players express).
- Full turn details (cards, guesses, errors) are visible via `history` after each turn resolves.
- `waiting_for` in the `waiting` phase is an empty list (no pending actions).
  In `active` phases, it lists players who have not yet submitted for the
  current turn/phase.

---

### 6.5 `submit_action` — CHANGED in v0.2

Submits a player's action for the current phase.

**Request:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `room_id` | string | yes | Room ID |
| `player_id` | string | yes | Your player name |
| `session_token` | string | yes | Session token (NEW) |
| `turn` | int | yes | Current turn number (NEW) |
| `phase` | string | yes | Current phase name (NEW) |
| `action` | string | yes | JSON string with action payload |

**Success Response:**

```json
{
  "protocol_version": "0.2",
  "accepted": true,
  "phase": "guess"
}
```

The `phase` field in the response reflects the phase AFTER processing.
If both players have submitted, this will be the next phase.
If only one player has submitted, this will be the current (unchanged) phase.

**Note:** The `accepted` response is advisory. Clients SHOULD call
`get_observation` to confirm the actual state.

**Errors:**

| Code | Condition |
|------|-----------|
| `ROOM_NOT_FOUND` | `room_id` does not exist |
| `INVALID_SESSION` | `session_token` invalid or does not match room |
| `WRONG_TURN` | `turn` does not match server's current turn |
| `WRONG_PHASE` | `phase` does not match server's current phase |
| `ALREADY_SUBMITTED` | Player already submitted for this turn/phase (same payload replay) |
| `ACTION_CONFLICT` | Player already submitted with a DIFFERENT payload |
| `INVALID_ACTION` | Action JSON malformed or missing required fields |

---

### 6.6 Idempotency Rules

**Idempotency key:** `(room_id, player_id, turn, phase)`

| Scenario | Server Response |
|----------|-----------------|
| First submission | `{protocol_version: "0.2", accepted: true, phase: ...}` |
| Replay with identical payload | Same success envelope including `protocol_version` (truly idempotent) |
| Replay with different payload | Error: `ACTION_CONFLICT` |

- `submit_action` is **at-most-once** per `(player_id, turn, phase)`.
- Same-payload replay returns a **success envelope** (not an error envelope).
  The server MUST store the accepted action payload to differentiate replays
  from conflicts.
- The canonical result includes only `{accepted, phase}`, not observation deltas.
- Clients that need current state MUST call `get_observation`.

**Implementation note:** v0.1 has no payload comparison — it raises
`RuntimeError` on any duplicate. v0.2 MUST store the submitted action to
enable same-payload vs different-payload distinction.

---

### 6.7 `get_history` — UNCHANGED in v0.2

Returns the full match history. No authentication required.

**Request:**

| Field | Type | Required |
|-------|------|----------|
| `room_id` | string | yes |

**Success Response:**

```json
{
  "protocol_version": "0.2",
  "config": { ... },
  "history": [ ... ],
  "phase": "final",
  "is_done": true,
  "pair_score": 32
}
```

**Errors:** `ROOM_NOT_FOUND`

---

### 6.8 `list_rooms` — UNCHANGED in v0.2

Lists all non-terminal rooms (`waiting` and `active`). `completed` rooms
are excluded. Expired rooms MAY appear until lazy cleanup runs.
No authentication required.

**Response:**

```json
{
  "protocol_version": "0.2",
  "rooms": [
    {
      "room_id": "a1b2c3d4",
      "config": { ... },
      "players": ["INANNA", "CARDMAN"],
      "phase": "express",
      "is_done": false
    }
  ]
}
```

---

### 6.9 `delete_room` — CHANGED in v0.2

Deletes a room. Requires session token of a player in the room.

**Request:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `room_id` | string | yes | Room ID |
| `session_token` | string | yes | Session token (NEW) |

**Success Response:**

```json
{
  "protocol_version": "0.2",
  "deleted": "a1b2c3d4"
}
```

**Errors:** `ROOM_NOT_FOUND`, `INVALID_SESSION`

---

## 7. Action Schemas

### 7.1 Express Phase

All fields are REQUIRED.

```json
{
  "expression": "coffee",
  "spoken_line": "I need this to wake up every morning...",
  "expression_reasoning": "Coffee represents a daily essential..."
}
```

| Field | Type | Constraint |
|-------|------|------------|
| `expression` | string | Non-empty. The item/word that represents the card value |
| `spoken_line` | string | Non-empty. In-character spoken line explaining the expression |
| `expression_reasoning` | string | Non-empty. Why this expression for this card value |

On Turn 1, the action MAY include an additional field:
- `interpretation`: string — the player's interpretation of the criterion (2-3 sentences)

### 7.2 Guess Phase

All fields are REQUIRED.

```json
{
  "my_guess": 8,
  "guess_reasoning": "The opponent's expression suggests...",
  "ragaman": false,
  "ragaman_reasoning": "The sum is unlikely to be 14..."
}
```

| Field | Type | Constraint |
|-------|------|------------|
| `my_guess` | int | 1 ≤ value ≤ 13 |
| `guess_reasoning` | string | Non-empty |
| `ragaman` | bool | Whether calling "Ragaman!" (sum = 14) |
| `ragaman_reasoning` | string | Non-empty |

On the guess phase, the action MAY include:
- `opponent_scale_reading`: string — reading of the opponent's expression before guessing

### 7.3 History Entry Schema

After each turn resolves, an entry is appended to `history`:

```json
{
  "turn": 1,
  "cards": {"INANNA": 13, "CARDMAN": 4},
  "expressions": {"INANNA": {...}, "CARDMAN": {...}},
  "guesses": {"INANNA": {...}, "CARDMAN": {...}},
  "actual_sum": 17,
  "is_ragaman": false,
  "errors": {"INANNA": 9, "CARDMAN": 3},
  "turn_score": 2,
  "pair_score_after": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `turn` | int | Turn number |
| `cards` | `{player_id: int}` | Both players' hidden cards |
| `expressions` | `{player_id: object}` | Both players' express actions |
| `guesses` | `{player_id: object}` | Both players' guess actions |
| `actual_sum` | int | Sum of both cards |
| `is_ragaman` | bool | Whether `actual_sum == 14` |
| `errors` | `{player_id: int}` | Absolute guess error per player |
| `turn_score` | int | Cooperative score for this turn |
| `pair_score_after` | int | Cumulative pair score after this turn |

---

## 8. Error Code Taxonomy

### 8.1 Client Errors

| Code | Description |
|------|-------------|
| `ROOM_NOT_FOUND` | Room ID does not exist or was deleted |
| `ROOM_FULL` | Room already has 2 players |
| `ROOM_EXPIRED` | Room was cleaned up by TTL |
| `UNSUPPORTED_MODE` | Unknown game_type or version |
| `INVALID_SESSION` | Session token invalid, expired, or mismatched |
| `ALREADY_SUBMITTED` | Same action replayed — returns **success envelope**, not error (see §6.6) |
| `ACTION_CONFLICT` | Different action for same turn/phase |
| `WRONG_TURN` | Turn number mismatch |
| `WRONG_PHASE` | Phase name mismatch |
| `INVALID_ACTION` | Action JSON malformed or missing required fields |
| `PLAYER_NOT_IN_ROOM` | `player_id` is not a participant in the specified room |

**Note:** `ALREADY_SUBMITTED` is not an error — the server returns the prior
canonical result as a **success envelope** (`{accepted: true, phase: ...}`),
making the operation truly idempotent from the client's perspective. It is
listed here for documentation purposes only; clients do not need to handle it
as an error case.

### 8.2 Server Errors

| Code | Description |
|------|-------------|
| `INTERNAL_ERROR` | Unexpected server failure |

Transport and runtime failures (network timeout, MCP framing errors) are
outside protocol scope.

---

## 9. TTL & Cleanup

- **Default TTL**: 600 seconds (10 minutes) from last activity.
- **Activity events**: `create_room`, `join_room`, `submit_action`.
  `get_observation` does NOT reset TTL (prevents third-party room extension
  since observation requires no authentication in v0.2).
- **Cleanup**: Server MAY clean up expired rooms at any time. In v0.1,
  cleanup only runs on `create_room`. v0.2 SHOULD run cleanup more
  frequently (e.g., on `list_rooms` or via background task).
- **No notification**: Clients discover expired rooms via `ROOM_NOT_FOUND` or `ROOM_EXPIRED`.
  Expired rooms MAY appear in `list_rooms` until lazy cleanup runs.
- **TTL as policy**: The 600-second value is a server default, not a protocol constant.
  Clients SHOULD NOT hardcode this value.

---

## 10. Consistency Model

- `get_observation` is the **authoritative source of truth** for game state.
- `submit_action` responses are **advisory** — they reflect the phase at the
  time of processing but may be stale if the other player submits concurrently.
- Clients SHOULD call `get_observation` after every `submit_action` to
  confirm state advancement.
- **Polling**: v0.2 is synchronous polling only. Clients poll `get_observation`
  to detect phase changes. Recommended intervals:
  - Awaiting opponent: 3-5 seconds
  - After own submission: 1 second (to detect phase advance)

---

## 11. Typical Session Flow

```
Client A                    Server                     Client B
   │                          │                           │
   ├─ create_room ──────────► │                           │
   │ ◄── {room_id, config} ── │                           │
   │                          │                           │
   ├─ join_room ────────────► │                           │
   │ ◄── {session_token_A} ── │                           │
   │                          │ ◄──────── join_room ──────┤
   │                          │ ── {session_token_B} ────►│
   │                          │                           │
   │   [phase: express, turn: 1]                          │
   │                          │                           │
   ├─ submit_action(express)─►│                           │
   │ ◄── {accepted, phase:    │                           │
   │      express} ────────── │                           │
   │                          │ ◄── submit_action(express)┤
   │                          │ ── {accepted, phase:      │
   │                          │     guess} ──────────────►│
   │                          │                           │
   │   [phase: guess — both expressions revealed]         │
   │                          │                           │
   ├─ get_observation ──────► │                           │
   │ ◄── {phase: guess,       │                           │
   │      expressions: {...}} │                           │
   │                          │                           │
   ├─ submit_action(guess) ─► │                           │
   │                          │ ◄──── submit_action(guess)┤
   │                          │                           │
   │   [turn resolves → next turn or final]               │
   │                          │                           │
   ├─ get_observation ──────► │                           │
   │ ◄── {phase: express,     │                           │
   │      turn: 2, ...}       │                           │
   ...                        ...                         ...
```

---

## 12. Migration Notes (v0.1 → v0.2)

| Change | v0.1 Behavior | v0.2 Behavior |
|--------|---------------|---------------|
| `session_token` | Not present | Returned by `join_room`, required for mutating ops |
| `submit_action` params | `(room_id, player_id, action)` | `+ session_token, turn, phase` |
| Error format | `{"error": "free text"}` | `{"error": {"code": "...", "message": "..."}}` |
| `protocol_version` | Not present | Included in all success responses |
| `get_observation` | Game fields only | `+ room_status, my_submission_state` |
| `create_room` | No version param | `+ version` param, `config` includes `version` field |
| `delete_room` | No auth | Requires `session_token` |
| Idempotency | Duplicate submit → RuntimeError | Same payload → prior success result; different → `ACTION_CONFLICT` |
| `ok` field | `join_room` returns `{"ok": true, ...}` | Removed — non-error response implies success |
| `reveal` phase | Dead code in `get_observation` (never entered) | Not included — use `history` for turn results |
| TTL activity | `create_room` + `submit_action` only | `+ join_room` also resets TTL (`get_observation` does NOT — prevents unauthenticated extension) |

---

## 13. Future Directions (v0.3+)

- **SSE event stream**: `subscribe_room` for push-based state updates
- **Public authentication**: Public key signing for multi-tenant deployment
- **Spectator mode**: Read-only observation for non-players
- **PersonaCard**: MCP Resource (`arena://persona/{name}`) for discovery
- **Multi-game**: Additional Game implementations beyond Ragaman
- **Narrator role**: Dedicated MCP client that transforms state into entertainment
