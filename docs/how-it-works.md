# How the profile art works

GitHub strips `<script>` and inline `style` attributes out of README
markdown, and runs no JavaScript. But it *does* render SVG referenced
from an `<img>` tag, and an SVG can carry its own `<style>` block with
CSS keyframes, plus SMIL `<animate>` elements. So the trick is to push
all the motion inside self-contained SVG files and let the README just
place them.

Nothing here calls a third-party badge service. That's deliberate: those
services rate-limit, cache aggressively, and go away (the widely-used
streak-stats endpoint broke for many profiles when Heroku ended its free
tier). The only external thing this repo touches is GitHub's own public
contributions HTML.

## The four pieces

| File | Source | Animation |
| --- | --- | --- |
| `portrait-ascii.svg` | `source-prepped.png` | Rows wipe in top to bottom, then freeze |
| `wordmark.svg` | the `AR` letterforms in `make_wordmark_svg.py` | Wipes in left to right, then rocks continuously |
| `info-card.svg` | `profile.json` | Rows slide in one after another |
| `contrib-heatmap.svg` | `data/contributions.json` | Cells pop in on a diagonal sweep |

Everything plays **once and holds** its final frame, except the
monogram's slow rock. A finished still is the resting state, which reads
calmer than a looping GIF and means a reader who arrives late isn't
staring at a blank box. Every file also honours
`prefers-reduced-motion: reduce` by collapsing its animation to
effectively zero duration, so readers who ask for stillness get the
finished frame immediately.

## Rebuilding

```sh
make          # redraw everything from committed sources
make data     # re-scrape the calendar only
make photo    # redo the portrait after replacing source-photo.jpg
```

`PALETTE=tokyo make` (or `mono`, or `hybrid`) switches the whole look.
Palettes live in `scripts/palettes.py`.

`make` and `make data` need only `requests`. `make photo` additionally
needs Pillow and numpy — which is why the prepped PNG is committed: the
daily job never has to install image libraries.

## Contribution data

`fetch_contributions.py` reads the public HTML at
`github.com/users/<user>/contributions`. No token, no GraphQL, no API
quota. Day cells carry `data-date` and `data-level`; the per-day counts
live in sibling `<tool-tip>` elements keyed by cell `id`, so the two are
joined on that id. Parsing is plain `re` rather than BeautifulSoup,
which keeps the Action's dependency list at exactly one package.

Derived stats (totals, active days, current and longest streak, best day,
busiest month) are computed once and stored alongside the raw days in
`data/contributions.json`, so the renderer never recomputes them.

One wrinkle worth knowing: the current streak skips a trailing empty
*today*. Without that, a live streak would read as zero every morning
until the day's first commit landed.

Because this is scraped rather than queried, it depends on GitHub's
markup. If the calendar ever renders blank, that's the first place to
look — `fetch_contributions.py` exits non-zero with a clear message when
it finds no day cells, rather than silently committing an empty graph.

## The portrait pipeline

`prep_photo.py` turns a snapshot into a clean grayscale bust:

1. **Crop** to head and shoulders. This matters more than it sounds — at
   ~100 characters wide, a full-body shot leaves a face perhaps 15 rows
   tall, which reads as nobody in particular.
2. **Matte** out the background. If `rembg` is installed it's used;
   otherwise a border-seeded flood fill grows inward from the frame
   edges under a colour-distance tolerance, which works because the
   background regions of a snapshot (sky, road, foliage) are each
   locally smooth while the subject's silhouette is a hard edge.
   Only the largest remaining blob is kept, which discards enclosed
   background — a patch of sky ringed by branches never touches the
   frame edge, so the fill can't reach it.
3. **Tone-map.** CLAHE for local contrast, blended back toward the
   original; then the subject's own histogram is stretched and squeezed
   into `[floor, ceil]`.

Two details in step 3 do most of the work. The **floor** keeps dark
clothing carrying enough ink to hold the silhouette instead of
dissolving into the page. The **ceiling** leaves headroom above skin
tone, so eyes, glasses and beard still modulate rather than all clipping
to the densest glyph. Pure CLAHE at full strength is actively wrong here:
it stretches a flat dark garment to near-white and drags whatever is
printed on it up into view.

The matte deliberately does **not** seed from the bottom edge. In a bust
crop the torso runs off the bottom of the frame, so seeding there lets
the fill march up through a flat garment and swallow the whole subject.

`make_ascii_svg.py` then maps brightness onto the ramp
`` " .`:-=+*cs#%@" ``. Two things are easy to get backwards:

- **Aspect.** A character cell is taller than it is wide, so the row
  count scales *down* by that ratio (~0.6). Divide instead of multiply
  and the face comes out stretched to roughly twice its height.
- **Polarity.** Drawing pale glyphs on a dark page, more ink reads as
  *more* light — so a bright pixel wants a *dense* glyph, and the matted
  background composites to black (not white) to stay inkless. Dark
  glyphs on white paper want the opposite; that's the `--dark-ink` flag.

## Replacing the photo

Drop a new `source-photo.jpg` in, retune `CROP` in the `Makefile`, and
run `make photo`. A shoulders-up shot against a plain wall converts far
better than a wide outdoor one: more of the character grid is spent on
the face, and there's no foliage for the matte to mistake for hair.

If the matte eats part of the subject, lower `--tol`; if background
survives, raise it. Dark hair against dark foliage is the hard case,
since raising the tolerance enough to remove the trees also starts
removing the hairline.

## Layout notes

The README uses a `<table>` for the hero row, because that's the only
reliable way to sit two images side by side in GitHub markdown. Widths
are chosen so the portrait (350px) plus the monogram (372px) span about
the same 735px as the calendar below, which keeps the block aligned.
Spacing uses `<br>` tags, since inline `style` is stripped. Headings are
`<h3>` — `<h1>` and `<h2>` draw a full-width underline rule that cuts
across the layout.
