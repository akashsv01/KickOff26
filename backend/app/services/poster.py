"""Server-side champagne-gold champion poster generation."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

POSTER_WIDTH = 1200
POSTER_HEIGHT = 630
CHAMPAGNE = (212, 175, 55)
DARK = (20, 20, 30)
LIGHT = (255, 250, 240)


def generate_champion_poster(
    champion_name: str,
    champion_code: str,
    subtitle: str = "2026 International Football Tournament",
    bracket_summary: str = "",
) -> bytes:
    """Generate PNG poster bytes for social sharing / download."""
    img = Image.new("RGB", (POSTER_WIDTH, POSTER_HEIGHT), DARK)
    draw = ImageDraw.Draw(img)

    # Gold border
    border = 8
    draw.rectangle(
        [border, border, POSTER_WIDTH - border, POSTER_HEIGHT - border],
        outline=CHAMPAGNE,
        width=border,
    )

    try:
        title_font = ImageFont.truetype("arial.ttf", 48)
        champ_font = ImageFont.truetype("arial.ttf", 72)
        sub_font = ImageFont.truetype("arial.ttf", 28)
        small_font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        title_font = ImageFont.load_default()
        champ_font = title_font
        sub_font = title_font
        small_font = title_font

    draw.text((POSTER_WIDTH // 2, 80), "KickOff26", fill=CHAMPAGNE, font=title_font, anchor="mm")
    draw.text((POSTER_WIDTH // 2, 160), subtitle, fill=LIGHT, font=sub_font, anchor="mm")
    draw.text((POSTER_WIDTH // 2, 280), "PREDICTED CHAMPION", fill=CHAMPAGNE, font=sub_font, anchor="mm")
    draw.text((POSTER_WIDTH // 2, 380), champion_name, fill=LIGHT, font=champ_font, anchor="mm")
    draw.text((POSTER_WIDTH // 2, 460), f"({champion_code})", fill=CHAMPAGNE, font=sub_font, anchor="mm")

    if bracket_summary:
        # Wrap bracket summary
        lines = _wrap_text(bracket_summary, 60)
        y = 520
        for line in lines[:3]:
            draw.text((POSTER_WIDTH // 2, y), line, fill=LIGHT, font=small_font, anchor="mm")
            y += 30

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    lines = []
    current = []
    for w in words:
        test = " ".join(current + [w])
        if len(test) <= width:
            current.append(w)
        else:
            if current:
                lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return lines
