"""Turn history entries → Discord Embed dicts.

Template-based narration (no LLM calls).
Returns plain dicts so this module has no discord.py dependency.
"""

from __future__ import annotations


def turn_embed(record: dict, player_names: list[str]) -> dict:
    """Create a Discord embed dict for one completed turn."""
    p1, p2 = player_names
    cards = record["cards"]
    exprs = record["expressions"]
    guesses = record["guesses"]
    errs = record["errors"]
    ts = record.get("turn_score", 0)
    ps = record.get("pair_score_after", 0)
    is_rg = record.get("is_ragaman", False)
    turn = record["turn"]

    # Color: green for good score, yellow for ok, red for bad
    color = 0x2ECC71 if ts >= 8 else (0xF1C40F if ts >= 4 else 0xE74C3C)

    title = f"Turn {turn}"
    if is_rg:
        title += "  RAGAMAN!"

    # Expression summary
    e1 = exprs.get(p1, {})
    e2 = exprs.get(p2, {})
    g1 = guesses.get(p1, {})
    g2 = guesses.get(p2, {})

    fields = [
        {
            "name": f"{p1} expressed (card {cards[p2]})",
            "value": f"**{e1.get('expression', '?')}**\n_{e1.get('spoken_line', '')}_",
            "inline": True,
        },
        {
            "name": f"{p2} expressed (card {cards[p1]})",
            "value": f"**{e2.get('expression', '?')}**\n_{e2.get('spoken_line', '')}_",
            "inline": True,
        },
        {"name": "\u200b", "value": "\u200b", "inline": False},  # spacer
        {
            "name": f"{p1} guessed own card",
            "value": f"{g1.get('my_guess', '?')} (actual: {cards[p1]}, error: {errs[p1]})",
            "inline": True,
        },
        {
            "name": f"{p2} guessed own card",
            "value": f"{g2.get('my_guess', '?')} (actual: {cards[p2]}, error: {errs[p2]})",
            "inline": True,
        },
    ]

    # Ragaman calls
    rg_parts = []
    if g1.get("ragaman"):
        rg_parts.append(f"{p1} called Ragaman! {'(correct)' if is_rg else '(wrong)'}")
    if g2.get("ragaman"):
        rg_parts.append(f"{p2} called Ragaman! {'(correct)' if is_rg else '(wrong)'}")
    if rg_parts:
        fields.append({
            "name": "Ragaman",
            "value": "\n".join(rg_parts),
            "inline": False,
        })

    description = f"Turn score: **{ts}** | Pair total: **{ps}**"

    return {
        "title": title,
        "description": description,
        "color": color,
        "fields": fields,
    }


def final_embed(history: list[dict], player_names: list[str],
                theme: str, criterion: str) -> dict:
    """Create a Discord embed dict for the final match result."""
    if not history:
        return {"title": "No turns played", "color": 0x95A5A6}

    p1, p2 = player_names
    pair_score = history[-1].get("pair_score_after", 0)
    max_possible = len(history) * 10
    pct = (pair_score / max_possible * 100) if max_possible else 0

    color = 0x2ECC71 if pct >= 70 else (0xF1C40F if pct >= 40 else 0xE74C3C)

    # Per-turn summary
    lines = []
    for h in history:
        rg = " RAGAMAN!" if h.get("is_ragaman") else ""
        lines.append(f"Turn {h['turn']}: +{h.get('turn_score', 0)}{rg}")

    return {
        "title": f"Match Complete: {p1} vs {p2}",
        "description": (
            f"**Theme:** {theme}\n"
            f"**Criterion:** {criterion}\n\n"
            f"**Pair Score: {pair_score} / {max_possible}** ({pct:.0f}%)"
        ),
        "color": color,
        "fields": [
            {
                "name": "Turn Summary",
                "value": "\n".join(lines) or "No turns",
                "inline": False,
            },
        ],
    }


def start_embed(theme: str, criterion: str, turns: int,
                player_names: list[str]) -> dict:
    """Create a Discord embed for match start announcement."""
    p1, p2 = player_names
    return {
        "title": f"Ragaman: {p1} vs {p2}",
        "description": (
            f"**Theme:** {theme}\n"
            f"**Criterion:** {criterion}\n"
            f"**Turns:** {turns}\n\n"
            "Match starting..."
        ),
        "color": 0x3498DB,
    }
