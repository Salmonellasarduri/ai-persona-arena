"""Generate OGP image (1200x630) from match result JSON.

Usage:
    python -m arena.ogp match_result.json
    python -m arena.ogp match_result.json -o card.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


W, H = 1200, 630
BG = (13, 17, 23)        # GitHub dark
TEXT = (230, 237, 243)
DIM = (139, 148, 158)
ACCENT = (88, 166, 255)
P1_COLOR = (218, 124, 255)
P2_COLOR = (121, 192, 255)
GREEN = (63, 185, 80)
YELLOW = (210, 153, 34)
RED = (248, 81, 73)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Try common fonts, fall back to default."""
    candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _load_jp_font(size: int) -> ImageFont.FreeTypeFont:
    """Japanese-capable font."""
    jp_candidates = [
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        "C:/Windows/Fonts/YuGothR.ttc",
    ]
    for path in jp_candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return _load_font(size)


def generate_ogp(history: list[dict], theme: str = "", criterion: str = "") -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    font_lg = _load_font(36)
    font_md = _load_jp_font(22)
    font_sm = _load_jp_font(16)
    font_num = _load_font(48)

    players = list(history[0]["cards"].keys()) if history else ["?", "?"]
    p1, p2 = players[0], players[1]

    # ── Header ──
    draw.text((40, 30), "AI PERSONA ARENA", fill=ACCENT, font=font_lg)
    draw.text((40, 75), f"{p1}  vs  {p2}", fill=TEXT, font=font_md)

    # Theme
    if theme or criterion:
        label = f"{theme} / {criterion}" if theme and criterion else (theme or criterion)
        draw.text((40, 110), label[:60], fill=DIM, font=font_sm)

    # ── Pair Score ──
    pair_score = history[-1].get("pair_score_after", 0) if history else 0
    max_score = len(history) * 10
    score_text = f"{pair_score}"
    draw.text((900, 30), score_text, fill=ACCENT, font=font_num)
    draw.text((900 + font_num.getlength(score_text) + 8, 55), f"/ {max_score}", fill=DIM, font=font_md)
    draw.text((900, 90), "pair score", fill=DIM, font=font_sm)

    # ── Divider ──
    draw.line([(40, 145), (W - 40, 145)], fill=(48, 54, 61), width=1)

    # ── Turn summaries ──
    y = 160
    for h in history[:5]:
        turn = h["turn"]
        cards = h["cards"]
        exprs = h["expressions"]
        errs = h["errors"]
        ts = h.get("turn_score", 0)

        # Turn number
        draw.text((40, y), f"T{turn}", fill=DIM, font=font_md)

        # Player 1 expression
        e1 = exprs.get(p1, {}).get("expression", "?")[:15]
        err1 = errs[p1]
        err1_color = GREEN if err1 == 0 else YELLOW if err1 <= 2 else RED
        draw.text((100, y), e1, fill=P1_COLOR, font=font_md)
        draw.text((100, y + 26), f"card:{cards[p1]} err:{err1}", fill=err1_color, font=font_sm)

        # Player 2 expression
        e2 = exprs.get(p2, {}).get("expression", "?")[:15]
        err2 = errs[p2]
        err2_color = GREEN if err2 == 0 else YELLOW if err2 <= 2 else RED
        draw.text((450, y), e2, fill=P2_COLOR, font=font_md)
        draw.text((450, y + 26), f"card:{cards[p2]} err:{err2}", fill=err2_color, font=font_sm)

        # Turn score + ragaman
        rg = " RGM!" if h.get("is_ragaman") else ""
        draw.text((800, y), f"+{ts}pts{rg}", fill=TEXT, font=font_md)

        y += 80

    # ── Best moment (lowest combined error) ──
    if history:
        best = min(history, key=lambda h: sum(h["errors"].values()))
        best_errs = sum(best["errors"].values())
        if best_errs <= 2:
            spoken = ""
            for pid in players:
                s = best["expressions"].get(pid, {}).get("spoken_line", "")
                if s:
                    spoken = s[:50] + ("..." if len(s) > 50 else "")
                    break
            if spoken:
                draw.text((40, H - 60), f'"{spoken}"', fill=DIM, font=font_sm)

    # ── Footer ──
    draw.text((W - 280, H - 30), "github.com/Salmonellasarduri/ai-persona-arena", fill=(68, 76, 86), font=font_sm)

    return img


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Generate OGP image from match result")
    parser.add_argument("input", help="match_result.json path")
    parser.add_argument("-o", "--output", default="ogp_card.png")
    parser.add_argument("--theme", default="")
    parser.add_argument("--criterion", default="")
    args = parser.parse_args()

    history = json.loads(Path(args.input).read_text(encoding="utf-8"))

    # Try to extract theme/criterion from history context
    theme = args.theme
    criterion = args.criterion

    img = generate_ogp(history, theme, criterion)
    img.save(args.output)
    print(f"OGP image saved: {args.output} ({W}x{H})")


if __name__ == "__main__":
    main()
