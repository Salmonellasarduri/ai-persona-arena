# ai-persona-arena

[日本語版 README はこちら](README_ja.md)

Lightweight game engine for AI personality battles.

> **Theme:** battle royale weapons / **Criterion:** happiness when distributed
>
> Both AIs see card 3 and card 1. Both express "landmine."
>
> **INANNA:** "地雷かあ...これって誰にとっても嫌なものよね。設置する人も使うのが怖いし、踏む人はもちろん最悪だし。"
>
> **CARDMAN:** "地雷であるな。こんなものを配布する業務があったら、苦情処理だけで一日が終わってしまうであろう。"
>
> INANNA guesses own card = 1 (actual: 1, **perfect read**)

Two AI personalities. Same question. Completely different reasoning.
The poet sees existential dread; the bureaucrat sees paperwork.

## What is this?

A game engine that makes AI characters play value-comparison games against each other. The first built-in game is **Ragaman** — a value-reading game:

1. A theme + criterion is announced (e.g. "drinks / want-to-drink-first-thing-in-the-morning level")
2. Each AI **expresses** the opponent's hidden number in their own words
3. Each AI **guesses** their own number from the opponent's expression
4. Your personality leaks through your expression. Precision wins.

## Quick start

```bash
# Clone and run
cd arena
pip install anthropic
export ANTHROPIC_API_KEY=sk-...

# Run a match: INANNA (poet) vs CARDMAN (bureaucrat)
python -m examples.run_match --theme "drinks" --criterion "want-to-drink-first-thing-in-the-morning level"

# Output: match_result.json + match_result.md
```

## Make your own AI player (5 minutes)

Copy `examples/simple_player.py` and edit the system prompt:

```python
from arena.players.base import LLMPlayer

MY_PROMPT = """
You are a lazy cat named Tama.
You see everything through the lens of napping, sunbeams, and fish.
"""

player = LLMPlayer(name="TAMA", system_prompt=MY_PROMPT)
```

That's it. Run `python -m examples.simple_player` to battle Cardman.

See [examples/simple_player.py](examples/simple_player.py) for the full working example.

## Add your own game

Subclass `Game` and implement 4 methods:

```python
from arena.engine import Game

class MyGame(Game):
    def setup(self, config: dict) -> dict:
        """Return initial game state."""

    def get_observation(self, state: dict, player_id: str) -> dict:
        """What can this player see right now?"""

    def apply_actions(self, state: dict, actions: dict) -> dict:
        """Both players committed — advance state."""

    def is_terminal(self, state: dict) -> bool:
        """Is the game over?"""
```

The engine handles simultaneous-commit (both players submit before either sees the other's move), turn management, and history tracking.

## Architecture

```
arena/
├── src/arena/
│   ├── engine.py          # Game engine (state machine + simultaneous commit)
│   ├── formatter.py       # Markdown output
│   ├── games/
│   │   └── ragaman.py     # Ragaman game rules
│   └── players/
│       ├── base.py        # Player base class + LLMPlayer
│       ├── inanna.py      # Poet personality
│       └── cardman.py     # Bureaucrat personality
├── examples/
│   ├── run_match.py       # Full match CLI
│   ├── simple_player.py   # Create your own player
│   └── mcp_client_demo.py # MCP protocol demo
└── viewer/
    └── index.html         # Browser-based match viewer
```

## Cost estimate

One 5-turn Ragaman match (2 players × 2 phases × 5 turns = 20 API calls):
- Claude Sonnet: ~$0.05
- Claude Haiku: ~$0.005

## Recommended models

| Model | Quality | Notes |
|-------|---------|-------|
| Claude Sonnet 4 | Best | Rich personality expression, accurate guessing |
| Claude Haiku 4.5 | Good | Faster, cheaper, slightly less personality depth |
| GPT-4o | Good | Works well, different flavor |
| Local LLMs (7B) | Varies | May struggle with JSON format and character consistency |

## MCP Server (remote play)

Run the game as an MCP server for remote AI agents:

```bash
# stdio (for Claude Desktop, Cursor, etc.)
python -m arena.server --transport stdio

# HTTP (for web clients)
python -m arena.server --transport streamable-http
```

Requires `pip install "ai-persona-arena[mcp]"`. See [examples/mcp_client_demo.py](examples/mcp_client_demo.py) for a full client example.

Available tools: `create_room`, `join_room`, `get_observation`, `submit_action`, `get_history`, `list_rooms`.

## Match Viewer

Open [viewer/index.html](viewer/index.html) in a browser and drop a `match_result.json` to see a visual replay.

## Roadmap

- [x] Game engine with simultaneous commit
- [x] Ragaman (value-reading game)
- [x] Built-in personalities (INANNA, CARDMAN)
- [x] Markdown match reports
- [x] MCP Server (remote play via Model Context Protocol)
- [x] Web match viewer
- [ ] More games (AI Bluff Poker, Wavelength variant, ...)
- [ ] Tournament mode

## License

MIT
