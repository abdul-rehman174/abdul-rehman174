"""Shared colour palettes for the generated profile SVGs.

One place to change the whole look. `ramp` is the 6-step heatmap scale
(level 0 = empty, 5 = an exceptional day); `ink` is body text, `dim` is
labels, `accent` is highlights, `bg` is the card background.
"""

PALETTES = {
    # Tokyo Night -- the palette already used across the profile.
    "tokyo": {
        "bg": "#1a1b27",
        "panel": "#1f2133",
        "ink": "#c0caf5",
        "dim": "#565f89",
        "accent": "#bb9af7",
        "accent2": "#7aa2f7",
        "accent3": "#7dcfff",
        "warn": "#f7768e",
        "ok": "#9ece6a",
        "ramp": ["#1f2133", "#3b3357", "#5a4a8f", "#7a5fc4", "#9d7bea", "#c3a6ff"],
        "ascii": "#c0caf5",
    },
    # Restrained terminal look: grey ASCII, GitHub-green calendar.
    "mono": {
        "bg": "#0d1117",
        "panel": "#161b22",
        "ink": "#c9d1d9",
        "dim": "#6e7681",
        "accent": "#c9d1d9",
        "accent2": "#8b949e",
        "accent3": "#58a6ff",
        "warn": "#f85149",
        "ok": "#39d353",
        "ramp": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"],
        "ascii": "#b9c0c8",
    },
    # Grey hero, Tokyo Night calendar and badges.
    "hybrid": {
        "bg": "#0d1117",
        "panel": "#161b22",
        "ink": "#c9d1d9",
        "dim": "#6e7681",
        "accent": "#bb9af7",
        "accent2": "#7aa2f7",
        "accent3": "#7dcfff",
        "warn": "#f7768e",
        "ok": "#9ece6a",
        "ramp": ["#161b22", "#2f2a45", "#4c3f7a", "#6d55b0", "#9077dd", "#bb9af7"],
        "ascii": "#b9c0c8",
    },
}


def get(name: str) -> dict:
    try:
        return PALETTES[name]
    except KeyError:
        raise SystemExit(f"unknown palette {name!r}; pick from {', '.join(PALETTES)}")
