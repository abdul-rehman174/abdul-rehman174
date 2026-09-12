#!/usr/bin/env python3
"""Scrape the public contribution calendar into data/contributions.json.

No token, no GraphQL, no third-party service -- just the public HTML at
github.com/users/<user>/contributions. Parsed with re instead of
BeautifulSoup so the Action needs nothing but `requests`.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import requests

UA = "Mozilla/5.0 (X11; Linux x86_64) profile-art/1.0"

# <td ... data-date="2026-01-05" id="contribution-day-component-3-1" data-level="2" ...>
CELL_RE = re.compile(
    r'<td[^>]*data-date="(?P<date>\d{4}-\d{2}-\d{2})"'
    r'[^>]*id="(?P<id>contribution-day-component-[\d-]+)"'
    r'[^>]*data-level="(?P<level>\d)"',
    re.I,
)
# <tool-tip ... for="contribution-day-component-3-1" ...>3 contributions on January 5th.</tool-tip>
TIP_RE = re.compile(
    r'<tool-tip[^>]*\sfor="(?P<id>contribution-day-component-[\d-]+)"[^>]*>'
    r'(?P<text>[^<]*)</tool-tip>',
    re.I,
)
COUNT_RE = re.compile(r"^([\d,]+)\s+contribution", re.I)


def fetch_html(user: str) -> str:
    url = f"https://github.com/users/{user}/contributions"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def parse(html: str) -> list[dict]:
    # id -> count, from the screen-reader tooltips
    counts: dict[str, int] = {}
    for m in TIP_RE.finditer(html):
        text = m.group("text").strip()
        cm = COUNT_RE.match(text)
        counts[m.group("id")] = int(cm.group(1).replace(",", "")) if cm else 0

    days: list[dict] = []
    for m in CELL_RE.finditer(html):
        cid = m.group("id")
        days.append(
            {
                "date": m.group("date"),
                "level": int(m.group("level")),
                "count": counts.get(cid, 0),
            }
        )
    days.sort(key=lambda d: d["date"])
    return days


def derive_stats(days: list[dict]) -> dict:
    total = sum(d["count"] for d in days)
    active = [d for d in days if d["count"] > 0]
    best = max(days, key=lambda d: d["count"]) if days else None

    # longest run of consecutive active days
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)

    # current streak counts back from the last day, but today having no
    # commits yet shouldn't zero out a live streak -- so skip a trailing
    # empty today and measure from yesterday.
    today = date.today().isoformat()
    tail = days[:-1] if days and days[-1]["date"] == today and days[-1]["count"] == 0 else days
    current = 0
    for d in reversed(tail):
        if d["count"] == 0:
            break
        current += 1

    months: dict[str, int] = {}
    for d in days:
        months[d["date"][:7]] = months.get(d["date"][:7], 0) + d["count"]

    return {
        "total": total,
        "active_days": len(active),
        "current_streak": current,
        "longest_streak": longest,
        "best_day": best,
        "busiest_month": max(months.items(), key=lambda kv: kv[1])[0] if months else None,
        "months": months,
        "first_date": days[0]["date"] if days else None,
        "last_date": days[-1]["date"] if days else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="abdul-rehman174")
    ap.add_argument("--out", default="data/contributions.json")
    ap.add_argument("--html", help="parse a local HTML file instead of fetching")
    args = ap.parse_args()

    html = Path(args.html).read_text(encoding="utf-8") if args.html else fetch_html(args.user)
    days = parse(html)
    if not days:
        raise SystemExit("no contribution cells found -- GitHub markup may have changed")

    payload = {
        "user": args.user,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": derive_stats(days),
        "days": days,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    s = payload["stats"]
    print(
        f"{len(days)} days -> {args.out}  "
        f"total={s['total']} active={s['active_days']} "
        f"cur={s['current_streak']} max={s['longest_streak']}"
    )


if __name__ == "__main__":
    main()
