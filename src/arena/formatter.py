"""Format match results as readable Markdown."""

from __future__ import annotations


def format_match_markdown(
    history: list[dict],
    theme: str,
    criterion: str,
    player_names: list[str],
) -> str:
    lines: list[str] = []
    w = lines.append

    p1, p2 = player_names
    w(f"# Ragaman Match: {p1} vs {p2}\n")
    w(f"**Theme:** {theme}  ")
    w(f"**Criterion:** {criterion}  ")
    w(f"**Turns:** {len(history)}\n")

    # Interpretations (from turn 1)
    if history:
        exprs = history[0]["expressions"]
        for pid in player_names:
            interp = exprs.get(pid, {}).get("interpretation", "")
            if interp:
                w(f"> **{pid}の解釈:** {interp}\n")

    for h in history:
        cards = h["cards"]
        exprs = h["expressions"]
        guesses = h["guesses"]
        is_rg = h["is_ragaman"]

        w(f"---\n## Turn {h['turn']}  {'🎯 RAGAMAN!' if is_rg else ''}\n")

        # Expression phase
        w("### Express\n")
        w(f"| | {p1} | {p2} |")
        w("|---|---|---|")
        w(f"| sees card | {cards[p2]} | {cards[p1]} |")
        w(f"| expression | **{exprs[p1].get('expression', '?')}** "
          f"| **{exprs[p2].get('expression', '?')}** |")

        for pid in player_names:
            expr = exprs.get(pid, {})
            spoken = expr.get("spoken_line", "")
            if spoken:
                w(f"\n**{pid}:** \"{spoken}\"\n")
            reason = expr.get("expression_reasoning", "")
            if reason:
                w(f"*({reason})*\n")

        # Guess phase
        w("### Guess\n")
        w(f"| | {p1} | {p2} |")
        w("|---|---|---|")
        w(f"| own card (hidden) | {cards[p1]} | {cards[p2]} |")

        g1 = guesses.get(p1, {})
        g2 = guesses.get(p2, {})
        w(f"| guessed | {g1.get('my_guess', '?')} | {g2.get('my_guess', '?')} |")
        w(f"| error | ±{h['errors'][p1]} | ±{h['errors'][p2]} |")

        rg1 = "YES" if g1.get("ragaman") else "-"
        rg2 = "YES" if g2.get("ragaman") else "-"
        w(f"| ragaman call | {rg1} | {rg2} |")

        # Guess reasoning
        for pid in player_names:
            g = guesses.get(pid, {})
            reading = g.get("opponent_scale_reading", "")
            reasoning = g.get("guess_reasoning", "")
            rg_reason = g.get("ragaman_reasoning", "")
            if reading or reasoning:
                w(f"\n**{pid}'s reasoning:**")
                if reading:
                    w(f"- Scale reading: {reading}")
                if reasoning:
                    w(f"- Guess: {reasoning}")
                if g.get("ragaman") and rg_reason:
                    correct = "✅" if is_rg else "❌"
                    w(f"- Ragaman call: {rg_reason} {correct}")
                w("")

        w(f"**Scores:** {h['scores_after']}\n")

    # Final
    if history:
        final = history[-1]["scores_after"]
        winner = max(final, key=final.get)
        w(f"---\n## Final Result\n")
        w(f"| Player | Score |")
        w(f"|--------|-------|")
        for pid in player_names:
            marker = " 👑" if pid == winner else ""
            w(f"| {pid} | {final[pid]}{marker} |")
        w(f"\n**Winner: {winner}**")

    return "\n".join(lines)
