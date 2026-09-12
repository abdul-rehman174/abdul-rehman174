#!/usr/bin/env python3
"""Turn a snapshot into a clean grayscale bust ready for ASCII conversion.

Run locally, once -- the output (source-prepped.png) is committed, so the
daily Action never needs image libraries.

Pipeline:
  crop -> background matte -> CLAHE local contrast -> composite on white

If `rembg` is importable it is used for the matte, since a real
segmentation model beats anything hand-rolled. Otherwise this falls back
to a border-seeded flood fill: the background regions of a snapshot
(sky, road, foliage) are each locally smooth, so growing a region inward
from the frame edge under a colour-distance tolerance captures them
while stopping at the subject's silhouette. Both paths feather the
resulting alpha so the ASCII edge doesn't come out jagged.

CLAHE is implemented directly (tile histogram equalisation with a clip
limit, bilinearly blended between tile centres) to avoid an OpenCV
dependency.
"""
from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


# ---------------------------------------------------------------- matte

def matte_rembg(img: Image.Image) -> np.ndarray | None:
    try:
        from rembg import remove  # type: ignore
    except Exception:
        return None
    out = remove(img.convert("RGBA"))
    return np.asarray(out)[:, :, 3].astype(np.float32) / 255.0


def keep_largest(mask: np.ndarray) -> np.ndarray:
    """Keep only the biggest blob -- the subject -- discarding stray islands.

    Enclosed background (a patch of sky ringed by branches) never touches
    the frame edge, so the flood fill can't reach it and it survives as
    a speck. Those specks read as grit in the ASCII, so drop everything
    that isn't the main silhouette.
    """
    h, w = mask.shape
    best: list[tuple[int, int]] = []
    seen = np.zeros((h, w), dtype=bool)
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or seen[sy, sx]:
                continue
            comp: list[tuple[int, int]] = []
            q = deque([(sy, sx)])
            seen[sy, sx] = True
            while q:
                y, x = q.popleft()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if len(comp) > len(best):
                best = comp
    out = np.zeros((h, w), dtype=bool)
    for y, x in best:
        out[y, x] = True
    return out


def matte_floodfill(
    img: Image.Image, tol: float, work: int = 320, edges: str = "top,left,right"
) -> np.ndarray:
    """Grow a background region inward from the frame border.

    Works on a downscaled copy (segmentation at 320px is far finer than
    the ~110-column ASCII grid needs) and compares each candidate pixel
    to its already-accepted neighbour, so smooth gradients like a sky
    are followed while a hard silhouette edge halts the fill.

    `edges` picks which borders to seed from. The bottom is excluded by
    default: in a head-and-shoulders crop the torso runs off the bottom
    of the frame, and seeding there lets the fill march up through a
    flat garment and swallow the whole subject.
    """
    want = {e.strip() for e in edges.split(",") if e.strip()}
    small = img.convert("RGB").resize((work, max(1, round(work * img.height / img.width))))
    a = np.asarray(small).astype(np.int16)
    h, w = a.shape[:2]

    bg = np.zeros((h, w), dtype=bool)
    seen = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()

    def seed(y: int, x: int) -> None:
        if not seen[y, x]:
            seen[y, x] = bg[y, x] = True
            q.append((y, x))

    if "top" in want:
        for x in range(w):
            seed(0, x)
    if "bottom" in want:
        for x in range(w):
            seed(h - 1, x)
    if "left" in want:
        for y in range(h):
            seed(y, 0)
    if "right" in want:
        for y in range(h):
            seed(y, w - 1)
    if not q:
        raise SystemExit(f"no seed edges selected from {edges!r}")

    t2 = tol * tol
    while q:
        y, x = q.popleft()
        ref = a[y, x]
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if ny < 0 or ny >= h or nx < 0 or nx >= w or seen[ny, nx]:
                continue
            d = a[ny, nx] - ref
            if int(d[0]) ** 2 + int(d[1]) ** 2 + int(d[2]) ** 2 <= t2:
                seen[ny, nx] = bg[ny, nx] = True
                q.append((ny, nx))

    alpha = keep_largest(~bg).astype(np.float32)

    # close pinholes inside the subject, then drop specks outside it
    am = Image.fromarray((alpha * 255).astype(np.uint8))
    am = am.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    am = am.resize((img.width, img.height), Image.BILINEAR)
    am = am.filter(ImageFilter.GaussianBlur(img.width / 260))
    return np.asarray(am).astype(np.float32) / 255.0


# --------------------------------------------------------------- CLAHE

def clahe(gray: np.ndarray, tiles: int = 8, clip: float = 2.5) -> np.ndarray:
    """Contrast-limited adaptive histogram equalisation, numpy only."""
    h, w = gray.shape
    g = (gray * 255).astype(np.uint8)
    ty, tx = max(1, h // tiles), max(1, w // tiles)
    ny, nx = max(1, h // ty), max(1, w // tx)

    # per-tile clipped CDF lookup tables
    luts = np.zeros((ny, nx, 256), dtype=np.float32)
    for i in range(ny):
        for j in range(nx):
            y0, y1 = i * ty, (i + 1) * ty if i < ny - 1 else h
            x0, x1 = j * tx, (j + 1) * tx if j < nx - 1 else w
            tile = g[y0:y1, x0:x1]
            hist = np.bincount(tile.ravel(), minlength=256).astype(np.float32)
            limit = clip * tile.size / 256.0
            excess = np.maximum(hist - limit, 0).sum()
            hist = np.minimum(hist, limit) + excess / 256.0
            cdf = np.cumsum(hist)
            luts[i, j] = cdf / max(cdf[-1], 1e-6)

    # bilinear blend of the four nearest tile LUTs
    yy = np.arange(h, dtype=np.float32) / ty - 0.5
    xx = np.arange(w, dtype=np.float32) / tx - 0.5
    yy = np.clip(yy, 0, ny - 1)
    xx = np.clip(xx, 0, nx - 1)
    y0 = np.floor(yy).astype(int)
    x0 = np.floor(xx).astype(int)
    y1 = np.minimum(y0 + 1, ny - 1)
    x1 = np.minimum(x0 + 1, nx - 1)
    fy = (yy - y0)[:, None]
    fx = (xx - x0)[None, :]

    idx = g
    def take(ti: np.ndarray, tj: np.ndarray) -> np.ndarray:
        return luts[ti[:, None], tj[None, :], idx]

    out = (
        take(y0, x0) * (1 - fy) * (1 - fx)
        + take(y0, x1) * (1 - fy) * fx
        + take(y1, x0) * fy * (1 - fx)
        + take(y1, x1) * fy * fx
    )
    return np.clip(out, 0, 1)


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--out", default="source-prepped.png")
    ap.add_argument("--crop", help="left,top,right,bottom in source pixels")
    ap.add_argument("--tol", type=float, default=26.0, help="flood-fill colour tolerance")
    ap.add_argument("--clip", type=float, default=2.5, help="CLAHE clip limit")
    ap.add_argument("--mix", type=float, default=0.4, help="CLAHE blend weight (0=off, 1=full)")
    ap.add_argument("--gamma", type=float, default=1.4,
                    help=">1 darkens midtones so skin lands mid-ramp instead of saturating")
    ap.add_argument("--floor", type=float, default=0.18,
                    help="lowest subject tone; keeps dark clothing from vanishing")
    ap.add_argument("--ceil", type=float, default=0.85,
                    help="highest subject tone; stops skin pinning to the densest glyph")
    ap.add_argument("--bg-level", type=float, default=0.0,
                    help="matted background tone: 1=white (dark ink), 0=black (light ink)")
    ap.add_argument("--width", type=int, default=760, help="working width")
    ap.add_argument("--edges", default="top,left,right",
                    help="which borders seed the flood fill")
    ap.add_argument("--no-matte", action="store_true", help="keep the background")
    args = ap.parse_args()

    img = Image.open(args.photo).convert("RGB")
    if args.crop:
        img = img.crop(tuple(int(v) for v in args.crop.split(",")))
    if img.width > args.width:
        img = img.resize((args.width, round(args.width * img.height / img.width)), Image.LANCZOS)

    if args.no_matte:
        alpha = np.ones((img.height, img.width), dtype=np.float32)
        how = "none"
    else:
        alpha = matte_rembg(img)
        how = "rembg"
        if alpha is None:
            alpha = matte_floodfill(img, args.tol, edges=args.edges)
            how = f"floodfill(tol={args.tol:g}, edges={args.edges})"

    gray = np.asarray(img.convert("L")).astype(np.float32) / 255.0
    # Blend the equalised image back toward the original. Pure CLAHE
    # stretches flat regions (a plain dark sweatshirt) to near-white and
    # drags up whatever texture is printed on them; mixing preserves the
    # global light-face / dark-torso relationship the ASCII ramp needs.
    gray = args.mix * clahe(gray, clip=args.clip) + (1.0 - args.mix) * gray

    # Normalise against the subject's own histogram, not the whole frame --
    # the matted background would otherwise anchor one end of the range and
    # flatten everything that matters.
    subject = alpha > 0.5
    if subject.any():
        lo, hi = np.percentile(gray[subject], (2, 98))
        gray = np.clip((gray - lo) / max(hi - lo, 1e-6), 0, 1)

    gray = np.clip(gray, 0, 1) ** args.gamma
    # Squeeze the subject into [floor, ceil]: the floor keeps a dark
    # garment carrying enough ink to hold the silhouette, the ceiling
    # leaves headroom above skin so eyes, glasses and beard still
    # modulate instead of all clipping to the densest glyph.
    gray = args.floor + gray * (args.ceil - args.floor)

    # Composite the cut-out onto a flat field. Which field depends on how
    # the ASCII will be drawn: light glyphs on a dark page mean ink ==
    # light, so the background must go to black (0) to stay inkless.
    comp = gray * alpha + args.bg_level * (1.0 - alpha)
    Image.fromarray((np.clip(comp, 0, 1) * 255).astype(np.uint8)).save(args.out)

    cover = float(alpha.mean())
    print(f"{args.out}  {img.width}x{img.height}  matte={how}  subject={cover * 100:.1f}% of frame")


if __name__ == "__main__":
    main()
