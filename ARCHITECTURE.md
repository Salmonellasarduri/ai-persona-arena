# Architecture

## Directory structure

```
ai-persona-arena/
├── src/arena/
│   ├── engine.py          # Game engine — state machine + simultaneous commit
│   ├── formatter.py       # Markdown match report generator
│   ├── ogp.py             # OGP image generator (1200×630)
│   ├── server.py          # MCP Server (FastMCP, 7 tools)
│   ├── games/
│   │   └── ragaman.py     # Ragaman — cooperative value-reading game
│   └── players/
│       ├── base.py        # Player ABC + LLMPlayer (Anthropic SDK)
│       ├── inanna.py      # Poet personality
│       └── cardman.py     # Bureaucrat personality
├── examples/
│   ├── run_match.py       # CLI: full match execution
│   ├── simple_player.py   # Minimal custom player example
│   └── mcp_client_demo.py # MCP client connection demo
├── viewer/
│   ├── index.html         # Browser match viewer (drag & drop JSON)
│   └── sample_match.json  # Auto-loaded sample data
└── tests/
    └── test_ragaman.py    # 14 unit tests (engine only, no LLM)
```

## Engine design

**Game** (ABC) defines the rules. **Room** manages the session.

```
Game.setup()          → initial state
Game.on_all_joined()  → deal cards
Game.get_observation() → what each player sees
Game.apply_actions()  → advance state after both commit
Game.is_terminal()    → game over?
```

Room handles the **simultaneous-commit pattern**: both players submit before either sees the other's action. Internally uses `_pending` dict → `_all_committed()` check → `apply_actions()`.

State is a plain `dict` (JSON-serializable). `copy.deepcopy` on every apply.

## MCP Server

FastMCP server exposing 7 tools:

| Tool | Description |
|------|-------------|
| `create_room` | Create a game room with theme/criterion |
| `join_room` | Join as a player |
| `get_observation` | See current game state (your view) |
| `submit_action` | Submit express/guess action |
| `get_history` | Full match history |
| `list_rooms` | List active rooms |
| `delete_room` | Clean up a room |

Transports: `stdio` (default), `sse`, `streamable-http`.

Room-level `asyncio.Lock` for concurrency safety. TTL-based cleanup (10 min).

## Viewer

Static HTML + vanilla JS. No build step, no dependencies.

- Drag & drop `match_result.json` to view
- Auto-loads `sample_match.json` if served via HTTP
- Dark theme, side-by-side player comparison
- All user content rendered via `textContent` (XSS-safe)
