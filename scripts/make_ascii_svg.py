#!/usr/bin/env python3
"""Convert the prepped bust into an ASCII-art SVG that types itself in.

Brightness is mapped onto a density ramp, then each row of characters
becomes one <text> element revealed by its own clip rect. The reveals
are staggered top-to-bottom, so the portrait appears to type in line by
line, then freezes -- no loop, which reads calmer than a GIF.

Character cells are taller than they are wide, so the image is sampled
with a matching aspect correction or the face comes out stretched.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import palettes

# light -> dark. Leading space means "paper", so the matted background
# costs nothing visually.
RAMP = " .`:-=+*cs#%@"


def to_rows(
    img: Image.Image, cols: int, cell_ratio: float, light_ink: bool = True
) -> list[str]:
    """Sample the image down to a character grid and map to the ramp.

    `light_ink` picks which way round density means brightness. Drawing
    pale glyphs on a dark page, more ink reads as more light, so a bright
    pixel wants a dense glyph. Dark glyphs on white paper want the
    opposite.
    """
    # A character cell is taller than it is wide (cell_ratio = w/h), so the
    # row count scales *down* by that ratio to keep the face in proportion.
    rows = max(1, round(cols * img.height / img.width * cell_ratio))
    small = img.convert("L").resize((cols, rows), Image.LANCZOS)
    a = np.asarray(small).astype(np.float32) / 255.0

    lum = a if light_ink else (1.0 - a)
    idx = np.clip(lum * (len(RAMP) - 1), 0, len(RAMP) - 1)
    idx = np.rint(idx).astype(int)
    return ["".join(RAMP[i] for i in row) for row in idx]


def trim(rows: list[str]) -> list[str]:
    """Drop fully blank edge rows and columns.

    The matte turns everything outside the subject into spaces, which
    would otherwise be baked into the canvas as dead margin -- the bust
    would then be scaled down to fit a box mostly full of nothing.
    """
    keep = [r for r in rows if r.strip()]
    if not keep:
        return rows
    width = max(len(r) for r in keep)
    keep = [r.ljust(width) for r in keep]
    left = min(len(r) - len(r.lstrip()) for r in keep)
    right = min(len(r) - len(r.rstrip()) for r in keep)
    return [r[left: width - right] for r in keep]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(
    rows: list[str],
    pal: dict,
    *,
    cell_w: float = 6.6,
    cell_h: float = 11.0,
    static: bool = False,
    label: str = "ASCII portrait",
    duration: float = 1.6,
) -> str:
    cols = max(len(r) for r in rows)
    rows = [r.ljust(cols) for r in rows]
    pad = 10
    art_w = cols * cell_w
    width = round(art_w + pad * 2)
    height = round(len(rows) * cell_h + pad * 2)

    mono = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
    per_row = duration / max(1, len(rows))
    wipe = 0.42

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(label)}">'
    )
    parts.append(f"<title>{esc(label)}</title>")

    if not static:
        defs = ["<defs>"]
        for r in range(len(rows)):
            y = pad + r * cell_h
            defs.append(
                f'<clipPath id="r{r}" clipPathUnits="userSpaceOnUse">'
                f'<rect x="{pad}" y="{y - cell_h:.1f}" height="{cell_h * 2.2:.1f}" width="0">'
                f'<animate attributeName="width" from="0" to="{art_w:.1f}" '
                f'dur="{wipe:.2f}s" begin="{0.1 + r * per_row:.2f}s" fill="freeze" '
                'calcMode="spline" keySplines="0.2 0.7 0.2 1" keyTimes="0;1" />'
                "</rect></clipPath>"
            )
        defs.append("</defs>")
        parts.append("".join(defs))

    for r, line in enumerate(rows):
        if not line.strip():
            continue
        clip = "" if static else f' clip-path="url(#r{r})"'
        parts.append(
            f'<text{clip} x="{pad}" y="{pad + (r + 1) * cell_h:.1f}" xml:space="preserve" '
            f'font-family="{mono}" font-size="{cell_h * 0.95:.1f}" '
            f'textLength="{art_w:.1f}" lengthAdjust="spacingAndGlyphs" '
            f'fill="{pal["ascii"]}">{esc(line)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="source-prepped.png")
    ap.add_argument("--out", default="portrait-ascii.svg")
    ap.add_argument("--palette", default="tokyo")
    ap.add_argument("--cols", type=int, default=104)
    ap.add_argument("--cell-ratio", type=float, default=0.6,
                    help="character cell width/height; corrects aspect")
    ap.add_argument("--label", default="ASCII portrait")
    ap.add_argument("--dark-ink", action="store_true",
                    help="invert density for dark glyphs on a light page")
    ap.add_argument("--no-trim", action="store_true",
                    help="keep blank margins instead of cropping to the subject")
    ap.add_argument("--static", action="store_true")
    ap.add_argument("--dump", action="store_true", help="also print the plain ASCII")
    args = ap.parse_args()

    img = Image.open(args.src)
    rows = to_rows(img, args.cols, args.cell_ratio, light_ink=not args.dark_ink)
    if not args.no_trim:
        rows = trim(rows)
    if args.dump:
        print("\n".join(rows))

    svg = render(rows, palettes.get(args.palette), static=args.static, label=args.label)
    Path(args.out).write_text(svg, encoding="utf-8")
    print(f"{args.out}  ({len(svg) / 1024:.1f} KB, {args.cols}x{len(rows)} chars, "
          f"palette={args.palette})")


if __name__ == "__main__":
    main()
