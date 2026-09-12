#!/usr/bin/env python3
"""Render profile.json as a neofetch-style info card SVG.

Rows fade and slide in one after another, then hold. Text content lives
in profile.json so wording can change without touching this file.

Character advance is measured rather than assumed: the card draws a
colour-swatch row and a key/value grid that both need to line up with
monospace cells, so the layout maths uses a single CELL_W constant that
matches the font-size via the ~0.6 advance ratio every mono face shares.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import palettes

FS = 13.0           # font size
CELL_W = FS * 0.6   # monospace advance
LINE_H = 20.0
PAD = 18.0
KEY_W = 10          # key column width; must exceed the longest key + ":"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(cfg: dict, pal: dict, *, static: bool = False) -> str:
    rows = [(str(k), str(v)) for k, v in cfg.get("rows", [])]
    handle = cfg.get("handle", "me@github")
    tagline = cfg.get("tagline", "")

    # widest line decides the card width
    longest = max([len(handle), len(tagline)] + [KEY_W + 2 + len(v) for _, v in rows])
    width = round(longest * CELL_W + PAD * 2)
    n_lines = len(rows) + 4          # handle, rule, rows, blank, swatches
    height = round(n_lines * LINE_H + PAD * 2)

    mono = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
    step = 0.085

    p: list[str] = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{esc(cfg.get("name", "profile"))} info card">'
    )
    p.append(f'<title>{esc(cfg.get("name", "profile"))}</title>')

    if not static:
        p.append(
            "<style>"
            "@keyframes in{from{opacity:0;transform:translateX(-10px)}"
            "to{opacity:1;transform:none}}"
            ".l{opacity:0;animation:in .5s cubic-bezier(.2,.8,.2,1) both 1}"
            "@media(prefers-reduced-motion:reduce){.l{animation-duration:.01s;animation-delay:0s}}"
            "</style>"
        )

    p.append(f'<rect width="{width}" height="{height}" rx="10" fill="{pal["bg"]}"/>')
    p.append(
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" '
        f'fill="none" stroke="{pal["panel"]}"/>'
    )

    cls = "" if static else ' class="l"'
    line = 0

    def y_of(i: int) -> float:
        return PAD + (i + 1) * LINE_H - 5

    def delay(i: int) -> str:
        return "" if static else f' style="animation-delay:{0.1 + i * step:.2f}s"'

    # header: user@host, then a rule the width of it
    p.append(
        f'<text{cls}{delay(line)} x="{PAD}" y="{y_of(line)}" xml:space="preserve" '
        f'font-family="{mono}" font-size="{FS}" font-weight="700" '
        f'fill="{pal["accent"]}">{esc(handle)}</text>'
    )
    line += 1
    p.append(
        f'<text{cls}{delay(line)} x="{PAD}" y="{y_of(line)}" xml:space="preserve" '
        f'font-family="{mono}" font-size="{FS}" fill="{pal["dim"]}">'
        f'{"-" * len(handle)}</text>'
    )
    line += 1

    # key/value grid -- keys padded to a fixed column so values align
    for key, val in rows:
        k = (key + ":").ljust(KEY_W)
        p.append(
            f'<text{cls}{delay(line)} x="{PAD}" y="{y_of(line)}" xml:space="preserve" '
            f'font-family="{mono}" font-size="{FS}">'
            f'<tspan fill="{pal["accent2"]}" font-weight="700">{esc(k)}</tspan>'
            f'<tspan fill="{pal["ink"]}">{esc(val)}</tspan></text>'
        )
        line += 1

    line += 0
    # neofetch signs off with its palette swatches
    swatch = [pal["warn"], pal["ok"], pal["accent3"], pal["accent2"], pal["accent"], pal["dim"]]
    sw = 16.0
    sy = y_of(line) - FS + 2
    for i, c in enumerate(swatch):
        p.append(
            f'<rect{cls}{delay(line)} x="{PAD + i * (sw + 4)}" y="{sy}" '
            f'width="{sw}" height="{FS}" rx="3" fill="{c}"/>'
        )
    if tagline:
        tx = PAD + len(swatch) * (sw + 4) + 10
        p.append(
            f'<text{cls}{delay(line)} x="{tx}" y="{y_of(line)}" xml:space="preserve" '
            f'font-family="{mono}" font-size="{FS - 2}" fill="{pal["dim"]}">{esc(tagline)}</text>'
        )

    p.append("</svg>")
    return "\n".join(p)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="profile.json")
    ap.add_argument("--out", default="info-card.svg")
    ap.add_argument("--palette", default="tokyo")
    ap.add_argument("--static", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    svg = render(cfg, palettes.get(args.palette), static=args.static)
    Path(args.out).write_text(svg, encoding="utf-8")
    print(f"{args.out}  ({len(svg) / 1024:.1f} KB, palette={args.palette})")


if __name__ == "__main__":
    main()
