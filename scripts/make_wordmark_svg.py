#!/usr/bin/env python3
"""Render a name as an extruded 3D ASCII wordmark SVG.

The letterforms come from a small hand-built block font. Depth is faked
the way ASCII art has always faked it: the same glyph stamped several
times on a diagonal offset, each copy dimmer than the one in front, so
the front face reads as a lit surface and the trailing copies as the
extruded side.

Two animations, in sequence:
  1. a left-to-right wipe (an expanding clip rect) types the mark in
  2. a slow "rock" -- horizontal squash plus a small skew, oscillating,
     which reads as the block turning on its vertical axis

SMIL is used rather than CSS keyframes for the rock because SMIL can
animate transform attributes on a group without needing transform-box
support, which Chrome and Firefox disagree about inside <img>.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import palettes

# 7-row block font. '#' is ink, space is air. Widths vary per letter;
# one blank column of padding is added between glyphs at render time.
FONT: dict[str, list[str]] = {
    "A": [" ####  ", "##  ## ", "##  ## ", "###### ", "##  ## ", "##  ## ", "##  ## "],
    "B": ["#####  ", "##  ## ", "##  ## ", "#####  ", "##  ## ", "##  ## ", "#####  "],
    "C": [" ##### ", "##     ", "##     ", "##     ", "##     ", "##     ", " ##### "],
    "D": ["#####  ", "##  ## ", "##  ## ", "##  ## ", "##  ## ", "##  ## ", "#####  "],
    "E": ["###### ", "##     ", "##     ", "#####  ", "##     ", "##     ", "###### "],
    "F": ["###### ", "##     ", "##     ", "#####  ", "##     ", "##     ", "##     "],
    "G": [" ##### ", "##     ", "##     ", "##  ###", "##   ##", "##   ##", " ##### "],
    "H": ["##  ## ", "##  ## ", "##  ## ", "###### ", "##  ## ", "##  ## ", "##  ## "],
    "I": ["###### ", "  ##   ", "  ##   ", "  ##   ", "  ##   ", "  ##   ", "###### "],
    "J": ["###### ", "    ## ", "    ## ", "    ## ", "##  ## ", "##  ## ", " ####  "],
    "K": ["##  ## ", "##  ## ", "## ##  ", "####   ", "## ##  ", "##  ## ", "##  ## "],
    "L": ["##     ", "##     ", "##     ", "##     ", "##     ", "##     ", "###### "],
    "M": ["##   ##", "### ###", "#######", "## # ##", "##   ##", "##   ##", "##   ##"],
    "N": ["##   ##", "###  ##", "#### ##", "## ####", "##  ###", "##   ##", "##   ##"],
    "O": [" ####  ", "##  ## ", "##  ## ", "##  ## ", "##  ## ", "##  ## ", " ####  "],
    "P": ["#####  ", "##  ## ", "##  ## ", "#####  ", "##     ", "##     ", "##     "],
    "Q": [" ####  ", "##  ## ", "##  ## ", "##  ## ", "## ### ", "##  ## ", " ## ## "],
    "R": ["#####  ", "##  ## ", "##  ## ", "#####  ", "## ##  ", "##  ## ", "##  ## "],
    "S": [" ##### ", "##     ", "##     ", " ####  ", "    ## ", "    ## ", "#####  "],
    "T": ["###### ", "  ##   ", "  ##   ", "  ##   ", "  ##   ", "  ##   ", "  ##   "],
    "U": ["##  ## ", "##  ## ", "##  ## ", "##  ## ", "##  ## ", "##  ## ", " ####  "],
    "V": ["##  ## ", "##  ## ", "##  ## ", "##  ## ", "##  ## ", " ####  ", "  ##   "],
    "W": ["##   ##", "##   ##", "##   ##", "## # ##", "#######", "### ###", "##   ##"],
    "X": ["##  ## ", "##  ## ", " ####  ", "  ##   ", " ####  ", "##  ## ", "##  ## "],
    "Y": ["##  ## ", "##  ## ", " ####  ", "  ##   ", "  ##   ", "  ##   ", "  ##   "],
    "Z": ["###### ", "    ## ", "   ##  ", "  ##   ", " ##    ", "##     ", "###### "],
    " ": ["    ", "    ", "    ", "    ", "    ", "    ", "    "],
    ".": ["   ", "   ", "   ", "   ", "   ", "## ", "## "],
    "-": ["      ", "      ", "      ", "##### ", "      ", "      ", "      "],
}

ROWS = 7


def layout(text: str) -> list[str]:
    """Stitch glyphs side by side into ROWS lines of ASCII.

    Each glyph carries a trailing blank column as letter spacing; the
    last one is trimmed so the mark isn't shoved off-centre by padding
    that textLength would then stretch across.
    """
    lines = [""] * ROWS
    for ch in text.upper():
        glyph = FONT.get(ch) or FONT[" "]
        for r in range(ROWS):
            lines[r] += glyph[r]
    width = max(len(l.rstrip()) for l in lines)
    return [l[:width].ljust(width) for l in lines]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(
    text: str,
    pal: dict,
    *,
    depth: int = 5,
    face_char: str = "#",
    side_char: str = "#",
    cell_w: float = 9.0,
    cell_h: float = 15.0,
    static: bool = False,
    mode: str = "rock",
) -> str:
    lines = layout(text)
    cols = max(len(l) for l in lines)
    lines = [l.ljust(cols) for l in lines]

    # The extrusion travels up-right. Its per-step offset has to scale
    # with the glyph, not sit at a fixed pixel count: a 3px step behind a
    # 29px character reads as motion blur, not depth.
    dx, dy = cell_w * 0.22, -cell_h * 0.13
    pad_x, pad_y = 16, 18
    art_w = cols * cell_w
    art_h = ROWS * cell_h
    width = int(art_w + pad_x * 2 + abs(dx) * depth)
    height = int(art_h + pad_y * 2 + abs(dy) * depth)

    mono = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
    base_x = pad_x
    base_y = pad_y + cell_h

    def mix(hex_a: str, hex_b: str, t: float) -> str:
        a = [int(hex_a[i : i + 2], 16) for i in (1, 3, 5)]
        b = [int(hex_b[i : i + 2], 16) for i in (1, 3, 5)]
        c = [round(a[i] + (b[i] - a[i]) * t) for i in range(3)]
        return "#%02x%02x%02x" % tuple(c)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(text)}">'
    )
    parts.append(f"<title>{esc(text)}</title>")

    # the wipe: a clip rect that grows from zero width to full
    if not static:
        parts.append(
            "<defs>"
            '<clipPath id="wipe" clipPathUnits="userSpaceOnUse">'
            f'<rect x="0" y="0" height="{height}" width="{"0" if not static else width}">'
            f'<animate attributeName="width" from="0" to="{width}" '
            'dur="1.15s" begin="0.15s" fill="freeze" '
            'calcMode="spline" keySplines="0.16 0.84 0.3 1" keyTimes="0;1" />'
            "</rect>"
            "</clipPath>"
            "</defs>"
        )

    open_g = '<g clip-path="url(#wipe)">' if not static else "<g>"
    parts.append(open_g)

    # the rock: squash horizontally and skew, pivoting on the mark's centre.
    # scale(<1) on x plus a skewY reads as the slab turning away from you.
    if not static and mode == "rock":
        cx, cy = width / 2, height / 2
        parts.append(f'<g transform="translate({cx:.1f} {cy:.1f})">')
        parts.append(
            '<g transform="scale(1 1)">'
            '<animateTransform attributeName="transform" type="scale" '
            'values="1 1;0.94 1;1 1;0.94 1;1 1" keyTimes="0;0.25;0.5;0.75;1" '
            'dur="7s" begin="1.3s" repeatCount="indefinite" additive="sum" />'
            '<animateTransform attributeName="transform" type="skewY" '
            'values="0;1.6;0;-1.6;0" keyTimes="0;0.25;0.5;0.75;1" '
            'dur="7s" begin="1.3s" repeatCount="indefinite" additive="sum" />'
        )
        parts.append(f'<g transform="translate({-cx:.1f} {-cy:.1f})">')
        depth_close = "</g></g></g>"
    else:
        depth_close = ""

    # extruded side, back-to-front so nearer copies paint over farther
    for d in range(depth, 0, -1):
        t = d / depth
        # Shade the extrusion from the face colour, not the accent -- a
        # monochrome hero has to stay monochrome even when the palette
        # carries a bright accent for use elsewhere.
        colour = mix(pal["ascii"], pal["bg"], 0.55 + 0.4 * t)
        ox = base_x + dx * d
        oy = base_y + dy * d
        for r, line in enumerate(lines):
            row = "".join(side_char if c == "#" else " " for c in line)
            if not row.strip():
                continue
            parts.append(
                f'<text x="{ox:.1f}" y="{oy + r * cell_h:.1f}" xml:space="preserve" '
                f'font-family="{mono}" font-size="{cell_h * 0.82:.1f}" '
                f'textLength="{art_w:.1f}" lengthAdjust="spacingAndGlyphs" '
                f'fill="{colour}">{esc(row)}</text>'
            )

    # lit front face
    for r, line in enumerate(lines):
        row = "".join(face_char if c == "#" else " " for c in line)
        if not row.strip():
            continue
        parts.append(
            f'<text x="{base_x:.1f}" y="{base_y + r * cell_h:.1f}" xml:space="preserve" '
            f'font-family="{mono}" font-size="{cell_h * 0.82:.1f}" font-weight="700" '
            f'textLength="{art_w:.1f}" lengthAdjust="spacingAndGlyphs" '
            f'fill="{pal["ascii"]}">{esc(row)}</text>'
        )

    parts.append(depth_close)
    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="ABDUL")
    ap.add_argument("--out", default="wordmark.svg")
    ap.add_argument("--palette", default="tokyo")
    ap.add_argument("--depth", type=int, default=5)
    ap.add_argument("--cell-w", type=float, default=9.0,
                    help="character cell width; raise it for a short monogram")
    ap.add_argument("--cell-h", type=float, default=15.0, help="character cell height")
    ap.add_argument("--mode", default="rock", choices=["rock", "still"])
    ap.add_argument("--face", default="#")
    ap.add_argument("--side", default="#")
    ap.add_argument("--static", action="store_true")
    args = ap.parse_args()

    svg = render(
        args.text,
        palettes.get(args.palette),
        depth=args.depth,
        face_char=args.face,
        side_char=args.side,
        cell_w=args.cell_w,
        cell_h=args.cell_h,
        static=args.static,
        mode=args.mode,
    )
    Path(args.out).write_text(svg, encoding="utf-8")
    print(f"{args.out}  ({len(svg) / 1024:.1f} KB, palette={args.palette}, text={args.text!r})")


if __name__ == "__main__":
    main()
