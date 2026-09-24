"""Gameplay derived from the music: every input lands on a real hit in the song.

Instead of drawing a shape and hoping it fits the song, these functions take the hit times
(from tools/analyze_song.py) and work out where the player is when each hit happens, then
return the geometry that makes that the only way through. The song never repeats a bar
exactly, so neither does the gameplay.

Movement rules per mode:
    wave    diagonal at exactly 1 row/column (mini: 2); every click reverses it. Exact.
    spider  teleports floor <-> ceiling instantly on click. Exact.
    cube    ballistic arcs; orb clicks restart the arc. APPROXIMATE - constants below are
            estimates, so orb chains leave slack and hazards stay clear of the arc.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .objects import SPEED_BLOCKS_PER_SECOND
from .sync import Timeline

# cube physics estimates, in blocks and seconds (jump ~2.1 high, ~0.39 s airtime)
GRAVITY = 114.0
JUMP_VELOCITY = 22.3
ORB_VELOCITY = {"yellow": 22.3, "pink": 16.0, "red": 30.0}


def load_hits(path: str | Path, band: str) -> list[float]:
    return json.loads(Path(path).read_text())["bands"][band]


def pick(hits: list[float], t0: float, t1: float, min_gap: float = 0.0,
         max_gap: float | None = None) -> list[float]:
    """Hits inside [t0, t1], thinned so consecutive ones are at least `min_gap` apart."""
    out: list[float] = []
    for h in sorted(hits):
        if not t0 <= h <= t1:
            continue
        if out and h - out[-1] < min_gap:
            continue
        out.append(h)
    return out


# ---------------------------------------------------------------- wave

@dataclass
class WavePath:
    points: list[tuple[float, float]]   # (column, row) at every turn
    clicks: list[float]                 # hit times actually used as inputs
    forced: int                         # turns the bounds forced off-beat (should be ~0)

    def __call__(self, x: float) -> float:
        pts = self.points
        if x <= pts[0][0]:
            return pts[0][1]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 <= x <= x1:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 > x0 else y1
        return pts[-1][1]


def wave_path(t: Timeline, hits: list[float], t0: float, t1: float, *, y0: float,
              lo: float, hi: float, rows_per_col: float = 1.0, start_up: bool = True
              ) -> WavePath:
    """A wave that reverses on the hits.

    Greedy: turn on every hit unless turning would carry it out of [lo, hi] before the next
    hit, in which case that hit is skipped. If even that fails, a turn is forced at the
    boundary (counted in `forced` so it's visible, not silent).
    """
    x, y = t.col_at_seconds(t0), y0
    d = 1 if start_up else -1
    pts, clicks, forced = [(x, y)], [], 0
    times = [h for h in sorted(hits) if t0 < h < t1] + [t1]
    for i, h in enumerate(times):
        hx = t.col_at_seconds(h)
        # travel to this hit, bouncing (forced) if a boundary comes first
        while True:
            target = y + d * rows_per_col * (hx - x)
            if lo <= target <= hi:
                x, y = hx, target
                break
            edge = hi if d > 0 else lo
            bx = x + (edge - y) / (d * rows_per_col)
            x, y = bx, edge
            pts.append((x, y))
            d, forced = -d, forced + 1
        if h == t1:
            pts.append((x, y))
            break
        nx = t.col_at_seconds(times[i + 1])
        turned = y - d * rows_per_col * (nx - hx)
        kept = y + d * rows_per_col * (nx - hx)
        if lo <= turned <= hi or not lo <= kept <= hi:
            pts.append((x, y))
            clicks.append(h)
            d = -d
    return WavePath(pts, clicks, forced)


# ---------------------------------------------------------------- spider

@dataclass
class SpiderRun:
    flips: list[tuple[float, str]]      # (column, side it flips TO) per click
    clicks: list[float]


def spider_run(t: Timeline, hits: list[float], t0: float, t1: float,
               start_side: str = "floor") -> SpiderRun:
    """One teleport per hit, alternating floor/ceiling."""
    side, flips, clicks = start_side, [], []
    for h in sorted(hits):
        if t0 < h < t1:
            side = "ceiling" if side == "floor" else "floor"
            flips.append((t.col_at_seconds(h), side))
            clicks.append(h)
    return SpiderRun(flips, clicks)


# ---------------------------------------------------------------- cube + orbs

@dataclass
class OrbChain:
    orbs: list[tuple[float, float, str]]        # (column, row, kind)
    platforms: list[tuple[float, float, float]] # (from column, to column, top row)
    clicks: list[float]                         # every input: orb clicks and jumps


def orb_chain(t: Timeline, hits: list[float], t0: float, t1: float, *, y0: float,
              lo: float, hi: float, kinds: list[str] | None = None,
              min_gap: float = 0.14) -> OrbChain:
    """Put an orb where the cube will be at each hit, starting with a jump at t0.

    A hit becomes an orb when the arc is inside [lo, hi] at that moment. When the arc would
    drop below `lo` before the next usable hit - real rhythms don't space themselves for a
    jump - the cube lands on a short platform instead and the next hit is a jump from it.
    So every input is still on a note, and physics error can't pile up across a platform.
    """
    kinds = kinds or ["yellow"]
    last_t, last_y, v = t0, y0, JUMP_VELOCITY
    orbs, platforms, clicks = [], [], [t0]

    def y_at(dt: float) -> float:
        return last_y + v * dt - GRAVITY * dt * dt / 2

    def time_to(row: float) -> float:
        """Seconds after the last input until the arc falls back to `row`."""
        a, b, c = -GRAVITY / 2, v, last_y - row
        disc = b * b - 4 * a * c
        return (-b - disc ** 0.5) / (2 * a) if disc >= 0 else 0.0

    for h in sorted(hits):
        if not t0 < h < t1:
            continue
        dt = h - last_t
        if dt < min_gap:
            continue
        y = y_at(dt)
        if lo <= y <= hi:
            kind = kinds[len(orbs) % len(kinds)]
            orbs.append((t.col_at_seconds(h), y, kind))
            clicks.append(h)
            last_t, last_y, v = h, y, ORB_VELOCITY.get(kind, JUMP_VELOCITY)
        elif y < lo:
            land = last_t + time_to(lo)
            platforms.append((t.col_at_seconds(land) - 0.5, t.col_at_seconds(h) + 0.5, lo))
            clicks.append(h)
            last_t, last_y, v = h, lo, JUMP_VELOCITY
    return OrbChain(orbs, platforms, clicks)
