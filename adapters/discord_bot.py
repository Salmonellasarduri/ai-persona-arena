"""Discord adapter for AI Persona Arena.

Run:
    ARENA_DISCORD_TOKEN=... python adapters/discord_bot.py

    For instant slash-command sync (recommended for dev):
    ARENA_DISCORD_TOKEN=... ARENA_DISCORD_GUILD=<guild_id> python adapters/discord_bot.py

Slash commands:
    /ragaman theme:drinks criterion:warmth turns:5
    /ragaman-stop

Requires: pip install discord.py>=2.3
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
from pathlib import Path

# Add src + project root to path
_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root / "src"))
sys.path.insert(0, str(_root))

import discord
from discord import app_commands

from arena.client import run_match_live
from adapters.narration import final_embed, start_embed, turn_embed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("arena.discord")

# ── State ──

_active_matches: dict[int, asyncio.Task] = {}  # channel_id → task
_match_history: dict[int, list[dict]] = {}  # channel_id → history
_match_names: dict[int, list[str]] = {}  # channel_id → player names

# ── Bot setup ──

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


@bot.event
async def on_ready():
    guild_id = os.environ.get("ARENA_DISCORD_GUILD")
    if guild_id:
        guild = discord.Object(id=int(guild_id))
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
        log.info("Arena bot ready as %s (synced to guild %s)", bot.user, guild_id)
    else:
        await tree.sync()
        log.info("Arena bot ready as %s (global sync — may take up to 1h)", bot.user)


@tree.command(name="ragaman", description="Start a Ragaman match (INANNA vs CARDMAN)")
@app_commands.describe(
    theme="Game theme (e.g. drinks, animals, emotions)",
    criterion="Ranking axis (e.g. cuteness level, want-to-drink level)",
    turns="Number of turns (1-10, default 5)",
)
async def cmd_ragaman(
    interaction: discord.Interaction,
    theme: str = "drinks",
    criterion: str = "want-to-drink-first-thing-in-the-morning level",
    turns: app_commands.Range[int, 1, 10] = 5,
):
    ch_id = interaction.channel_id

    if ch_id in _active_matches:
        await interaction.response.send_message(
            "A match is already running in this channel. Use `/ragaman-stop` to cancel.",
            ephemeral=True,
        )
        return

    await interaction.response.defer()

    task = asyncio.create_task(
        _run_match_in_channel(interaction, theme, criterion, turns)
    )
    _active_matches[ch_id] = task

    def _cleanup(t: asyncio.Task):
        _active_matches.pop(ch_id, None)
        if t.cancelled():
            log.info("Match in channel %s was cancelled", ch_id)
        elif t.exception():
            log.error("Match in channel %s failed: %s", ch_id, t.exception())

    task.add_done_callback(_cleanup)


@tree.command(name="ragaman-stop", description="Cancel the running match in this channel")
async def cmd_ragaman_stop(interaction: discord.Interaction):
    ch_id = interaction.channel_id
    task = _active_matches.get(ch_id)
    if not task:
        await interaction.response.send_message("No match running.", ephemeral=True)
        return

    task.cancel()
    _active_matches.pop(ch_id, None)
    await interaction.response.send_message("Match cancelled.")


# ── Match runner ──

async def _run_match_in_channel(
    interaction: discord.Interaction,
    theme: str,
    criterion: str,
    turns: int,
):
    ch = interaction.channel
    ch_id = interaction.channel_id
    names = ["INANNA", "CARDMAN"]
    _match_names[ch_id] = names

    # Start announcement
    embed = discord.Embed.from_dict(start_embed(theme, criterion, turns, names))
    await interaction.followup.send(embed=embed)

    async def on_turn(record: dict, player_names: list[str]):
        """Post turn narration to the channel."""
        e = discord.Embed.from_dict(turn_embed(record, player_names))
        await ch.send(embed=e)

    try:
        history = await run_match_live(
            theme=theme,
            criterion=criterion,
            turns=turns,
            on_turn=on_turn,
            turn_timeout=60.0,
        )
    except asyncio.CancelledError:
        await ch.send("Match was cancelled.")
        return
    except asyncio.TimeoutError:
        await ch.send("Match timed out (LLM response too slow).")
        return
    except Exception as exc:
        log.error("Match error: %s", exc, exc_info=True)
        await ch.send(f"Match failed: {exc}")
        return
    finally:
        _match_history.pop(ch_id, None)
        _match_names.pop(ch_id, None)

    # Final result
    fe = discord.Embed.from_dict(final_embed(history, names, theme, criterion))
    json_bytes = json.dumps(history, ensure_ascii=False, indent=2).encode("utf-8")
    file = discord.File(io.BytesIO(json_bytes), filename="match_result.json")
    await ch.send(embed=fe, file=file)


# ── Entry point ──

def _load_env():
    """Load .env from project root if it exists."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:  # don't override explicit env
            os.environ[key] = value


def main():
    _load_env()
    token = os.environ.get("ARENA_DISCORD_TOKEN")
    if not token:
        print("ARENA_DISCORD_TOKEN not set.")
        print("Create .env in project root with:")
        print("  ARENA_DISCORD_TOKEN=your_token_here")
        print("  ARENA_DISCORD_GUILD=your_guild_id_here")
        sys.exit(1)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
