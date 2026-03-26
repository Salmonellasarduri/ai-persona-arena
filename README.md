# ai-persona-arena

[日本語版 README はこちら](README_ja.md)

> AI personality x value reading — make your own AI play in 5 minutes

When AI personalities differ, even "landmine" means something different.
This engine turns that gap into a game.

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
This is Ragaman. Personality becomes the game.

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

That's it. Run `PYTHONPATH=src python -m examples.simple_player` to battle Cardman.

## Quick start

```bash
git clone https://github.com/Salmonellasarduri/ai-persona-arena.git
cd ai-persona-arena
pip install anthropic pillow
export ANTHROPIC_API_KEY=sk-...

# Run a match: INANNA (poet) vs CARDMAN (bureaucrat)
PYTHONPATH=src python -m examples.run_match --theme "drinks" --criterion "want-to-drink-first-thing-in-the-morning level"
```

Rules (cooperative, [ito](https://boardgamegeek.com/boardgame/262988/ito)-like): a theme + criterion is announced → each AI honestly expresses the opponent's hidden number in their own words → each guesses their own number from the opponent's expression → pair score measures mutual understanding. No deception — the fun is in the gap.

Output: `match_result.json` + `match_result.md`

## Share on X / Twitter

```bash
PYTHONPATH=src python -m arena.ogp match_result.json --theme "drinks" --criterion "want-to-drink-first-thing-in-the-morning level"
# → ogp_card.png (1200×630)
```

## Roadmap — want to help?

v0.1 shipped: game engine (simultaneous commit), Ragaman, built-in personalities (INANNA/CARDMAN), Markdown reports, MCP Server, web viewer, OGP card generator.

- [ ] More games (competitive reading mode, Wavelength variant, ...)
- [ ] Tournament mode

Issues, PRs, and new game ideas are welcome.

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

The engine handles simultaneous-commit, turn management, and history tracking.

## Details

- [Architecture](ARCHITECTURE.md) — directory structure, MCP Server, viewer
- [Cost estimate](#cost-estimate) / [Recommended models](#recommended-models)

## MCP Server (remote play)

Run the game as an MCP server for remote AI agents:

```bash
PYTHONPATH=src python -m arena.server --transport stdio            # Claude Desktop, Cursor
PYTHONPATH=src python -m arena.server --transport streamable-http  # Web
```

Requires `pip install mcp`. See [examples/mcp_client_demo.py](examples/mcp_client_demo.py).

## Match Viewer

Open [viewer/index.html](viewer/index.html) in a browser and drop a `match_result.json`.

## Cost estimate

One 5-turn match (20 API calls): Claude Sonnet ~$0.05 / Haiku ~$0.005

## Recommended models

| Model | Quality | Notes |
|-------|---------|-------|
| Claude Sonnet 4 | Best | Rich personality expression, accurate guessing |
| Claude Haiku 4.5 | Good | Faster, cheaper |
| GPT-4o | Good | Different flavor |
| Local LLMs (7B) | Varies | May struggle with JSON and character consistency |

## License

MIT
