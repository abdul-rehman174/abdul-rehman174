#!/usr/bin/env python3
"""Render data/contributions.json as an animated calendar heatmap SVG.

Cells reveal on a diagonal sweep (top-left to bottom-right) via CSS
keyframes embedded in the SVG, then freeze -- `animation-fill-mode:
both` plus a single iteration, so the finished graph is the resting
state. GitHub strips <script> and inline style attributes from READMEs
but honours <style> inside an <img>-referenced SVG.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import palettes

CELL = 13          # cell pitch
BOX = 11           # drawn box
RADIUS = 2.5
LEFT = 30          # room for weekday labels
TOP = 34           # room for month labels
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}


def build_weeks(days: list[dict]) -> list[list[dict | None]]:
    """Bucket days into GitHub-style columns; weeks start on Sunday."""
    weeks: list[list[dict | None]] = []
    col: list[dict | None] = []
    first_dow = (date.fromisoformat(days[0]["date"]).weekday() + 1) % 7
    col.extend([None] * first_dow)
    for d in days:
        col.append(d)
        if len(col) == 7:
            weeks.append(col)
            col = []
    if col:
        col.extend([None] * (7 - len(col)))
        weeks.append(col)
    return weeks


def month_labels(weeks: list[list[dict | None]]) -> list[tuple[int, str]]:
    """(column index, label) for each month's first appearance."""
    out: list[tuple[int, str]] = []
    seen: set[str] = set()
    for x, col in enumerate(weeks):
        first = next((c for c in col if c), None)
        if not first:
            continue
        ym = first["date"][:7]
        if ym in seen:
            continue
        seen.add(ym)
        # only label once there's room for the text
        if out and x - out[-1][0] < 3:
            continue
        out.append((x, MONTHS[int(ym[5:7]) - 1]))
    return out


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def pretty_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def render(payload: dict, pal: dict, *, static: bool, title: str) -> str:
    days = payload["days"]
    stats = payload["stats"]
    weeks = build_weeks(days)

    grid_w = len(weeks) * CELL
    width = LEFT + grid_w + 16
    footer_h = 46
    height = TOP + 7 * CELL + footer_h

    # diagonal reveal: delay grows with (col + row)
    span = len(weeks) + 7
    step = 0.9 / span          # whole sweep ~0.9s
    dur = 0.42

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{esc(title)}: {stats["total"]} contributions in the last year">'
    )
    parts.append(f"<title>{esc(title)}</title>")

    if not static:
        parts.append(
            "<style>"
            "@keyframes pop{from{opacity:0;transform:translateY(-4px) scale(.55)}"
            "to{opacity:1;transform:none}}"
            "@keyframes fade{from{opacity:0}to{opacity:1}}"
            ".c{opacity:0;animation:pop %.2fs cubic-bezier(.2,.9,.3,1.3) both 1;"
            "transform-origin:50%% 50%%;transform-box:fill-box}"
            ".t{opacity:0;animation:fade .5s ease both 1}"
            "@media(prefers-reduced-motion:reduce){"
            ".c,.t{animation-duration:.01s;animation-delay:0s}}"
            "</style>" % dur
        )

    parts.append(f'<rect width="{width}" height="{height}" rx="8" fill="{pal["bg"]}"/>')

    mono = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
    tcls = "" if static else ' class="t"'

    # month labels
    for x, label in month_labels(weeks):
        delay = "" if static else f' style="animation-delay:{x * step:.2f}s"'
        parts.append(
            f'<text{tcls}{delay} x="{LEFT + x * CELL}" y="{TOP - 12}" '
            f'fill="{pal["dim"]}" font-family="{mono}" font-size="10">{label}</text>'
        )

    # weekday labels
    for row, label in DAY_LABELS.items():
        delay = "" if static else f' style="animation-delay:{row * step:.2f}s"'
        parts.append(
            f'<text{tcls}{delay} x="{LEFT - 8}" y="{TOP + row * CELL + BOX - 2}" '
            f'text-anchor="end" fill="{pal["dim"]}" font-family="{mono}" '
            f'font-size="9">{label}</text>'
        )

    # cells
    ramp = pal["ramp"]
    best = (stats.get("best_day") or {}).get("count", 0)
    for x, col in enumerate(weeks):
        for y, cell in enumerate(col):
            if cell is None:
                continue
            level = cell["level"]
            # promote a personal-best day to the brightest step
            if best and cell["count"] == best and best > 0:
                level = 5
            fill = ramp[min(level, len(ramp) - 1)]
            cx = LEFT + x * CELL
            cy = TOP + y * CELL
            cls = "" if static else ' class="c"'
            delay = "" if static else f' style="animation-delay:{(x + y) * step:.2f}s"'
            n = cell["count"]
            tip = "no contributions" if n == 0 else f"{n} contribution{'s' if n != 1 else ''}"
            parts.append(
                f'<rect{cls}{delay} x="{cx}" y="{cy}" width="{BOX}" height="{BOX}" '
                f'rx="{RADIUS}" fill="{fill}">'
                f"<title>{tip} on {pretty_date(cell['date'])}</title></rect>"
            )

    # footer: summary line left, Less->More legend right
    fy = TOP + 7 * CELL + 26
    fdelay = "" if static else ' style="animation-delay:1.0s"'
    summary = (
        f'<tspan fill="{pal["accent"]}">{stats["total"]:,}</tspan> contributions  '
        f'·  <tspan fill="{pal["accent2"]}">{stats["longest_streak"]}</tspan> day best streak  '
        f'·  <tspan fill="{pal["accent3"]}">{stats["active_days"]}</tspan> active days'
    )
    parts.append(
        f'<text{tcls}{fdelay} x="{LEFT}" y="{fy}" fill="{pal["dim"]}" '
        f'font-family="{mono}" font-size="11">{summary}</text>'
    )

    lx = LEFT + grid_w - (len(ramp) * 12 + 66)
    parts.append(
        f'<text{tcls}{fdelay} x="{lx}" y="{fy}" fill="{pal["dim"]}" '
        f'font-family="{mono}" font-size="10">Less</text>'
    )
    for i, c in enumerate(ramp):
        parts.append(
            f'<rect{tcls}{fdelay} x="{lx + 30 + i * 12}" y="{fy - 8}" width="9" height="9" '
            f'rx="2" fill="{c}"/>'
        )
    parts.append(
        f'<text{tcls}{fdelay} x="{lx + 36 + len(ramp) * 12}" y="{fy}" fill="{pal["dim"]}" '
        f'font-family="{mono}" font-size="10">More</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/contributions.json")
    ap.add_argument("--out", default="contrib-heatmap.svg")
    ap.add_argument("--palette", default="tokyo")
    ap.add_argument("--title", default="GitHub contributions")
    ap.add_argument("--static", action="store_true", help="no animation (preview frame)")
    args = ap.parse_args()

    payload = json.loads(Path(args.data).read_text(encoding="utf-8"))
    svg = render(payload, palettes.get(args.palette), static=args.static, title=args.title)
    Path(args.out).write_text(svg, encoding="utf-8")
    print(f"{args.out}  ({len(svg) / 1024:.1f} KB, palette={args.palette})")


if __name__ == "__main__":
    main()
