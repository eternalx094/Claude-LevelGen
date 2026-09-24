"""Estimate how tight a level actually is, in frames.

Measured from the built geometry, not from intent: for every column we find the passage the
player has to fit through, subtract the hitbox, and convert the leftover slack into time at
the speed that applies there. Slack that lasts less than one frame at a given refresh rate
is a frame perfect at that rate.

    window_seconds = (passage - hitbox) / speed_in_blocks_per_second
    frames(fps)    = window_seconds * fps        # <= 1 means frame perfect

This is an estimate of *spatial* tightness. It does not simulate jumps, so cube timing and
orb chains are under-counted, and it says nothing about how hard a pattern is to read.
Treat it as a tightness map to aim playtesting at, not a difficulty verdict.
"""
from __future__ import annotations

import math
from collections import defaultdict

from . import objects as O
from .level import Level
from .sync import Timeline

# how much vertical room the player needs, in blocks
HITBOX = {"cube": 1.0, "ship": 0.95, "ball": 1.0, "ufo": 1.0, "robot": 1.0,
          "spider": 1.0, "wave": 0.35, "swing": 0.95}
CEILING = 14


SPIKE_HITBOX = 0.6   # a spike's hitbox is smaller than its cell
SAMPLES_PER_COLUMN = 2


def occupancy(level: Level) -> dict[int, list[tuple[float, float, float, float]]]:
    """Blocked boxes (x0, x1, y0, y1) in blocks, bucketed by column - real geometry, so
    fractional placements are measured as they are, not rounded to the grid."""
    grid: dict[int, list[tuple[float, float, float, float]]] = defaultdict(list)
    for o in level.objects:
        cat = O.category(o.id)
        if cat not in ("solid", "hazard", "saw"):
            continue
        sx = float(o.get("128", o.get("32", 1)))
        sy = float(o.get("129", o.get("32", 1)))
        cx, cy = o.gx / 30, o.gy / 30
        if cat == "saw":
            r = O.SAWS[o.id] * sx
            box = (cx - r, cx + r, cy - r, cy + r)
        elif cat == "hazard":
            h = SPIKE_HITBOX * O.hazard_height(o.id) * sy
            box = (cx - 0.35 * sx, cx + 0.35 * sx, cy - h / 2, cy + h / 2)
        else:
            box = (cx - 0.5 * sx, cx + 0.5 * sx, cy - 0.5 * sy, cy + 0.5 * sy)
        for col in range(math.floor(box[0]), math.ceil(box[1]) + 1):
            grid[col].append(box)
    return grid


def free_intervals(boxes: list[tuple[float, float, float, float]], x: float
                   ) -> list[tuple[float, float]]:
    """Clear vertical gaps at x, from the ground up to the ceiling."""
    spans = sorted((b[2], b[3]) for b in boxes if b[0] <= x <= b[1])
    out, y = [], 0.0
    for lo, hi in spans:
        if lo > y:
            out.append((y, lo))
        y = max(y, hi)
    if y < CEILING:
        out.append((y, CEILING))
    return out


def follow(intervals: list[tuple[float, float]], current: tuple[float, float],
           hitbox: float = 1.0) -> tuple[float, float]:
    """Pick the gap the player is actually travelling in: the one that overlaps where they
    were, else the nearest. Stops the measurement drifting into the open sky above a
    corridor, or into a crevice too small to be in (the slot between a platform and the
    spike standing on it) - neither is a passage anyone flies through."""
    usable = [iv for iv in intervals if iv[1] - iv[0] >= hitbox * 0.9]
    intervals = usable or intervals
    if not intervals:
        return current
    lo, hi = current

    def overlap(iv):
        return min(hi, iv[1]) - max(lo, iv[0])

    best = max(intervals, key=overlap)
    if overlap(best) > 0:
        return best
    mid = (lo + hi) / 2
    return min(intervals, key=lambda iv: abs((iv[0] + iv[1]) / 2 - mid))


def spots(level: Level, t: Timeline, x0: float, x1: float, fps: int,
          mode_at: dict[int, str] | None = None, grid=None) -> tuple[int, int]:
    """(tight places, inputs inside them) between two columns, at one refresh rate.

    A "place" is a contiguous stretch whose window is under one frame - roughly one
    obstacle. "Inputs" counts the direction changes the player has to make inside those
    stretches, which is closer to what people mean by a level's frame-perfect count.
    """
    grid = grid if grid is not None else occupancy(level)
    count, inputs, inside = 0, 0, False
    prev_centre, prev_dir = None, 0
    step = 1.0 / SAMPLES_PER_COLUMN
    x = float(int(x0))
    lane = (0.0, 1.0)                     # the player starts on the ground
    while x <= x1:
        boxes = grid.get(math.floor(x))
        if not boxes:
            inside = False
            x += step
            continue
        mode = (mode_at or {}).get(math.floor(x), "cube")
        hitbox = HITBOX.get(mode, 1.0)
        lane = follow(free_intervals(boxes, x), lane, hitbox)
        slack = (lane[1] - lane[0]) - hitbox
        speed = O.SPEED_BLOCKS_PER_SECOND[t.speed_at(t.beat_at_col(x))]
        frames = max(0.0, slack) / speed * fps
        centre = (lane[0] + lane[1]) / 2
        direction = 0 if prev_centre is None or abs(centre - prev_centre) < 1e-6 else (
            1 if centre > prev_centre else -1)
        if frames <= 1.0 + 1e-9:
            if not inside:
                count += 1
            if direction and prev_dir and direction != prev_dir:
                inputs += 1
            inside = True
        else:
            inside = False
        if direction:
            prev_dir = direction
        prev_centre = centre
        x += step
    return count, inputs


def mode_map(level: Level, x0: float, x1: float, start_mode: str = "cube") -> dict[int, str]:
    """Which gamemode applies at each column, following the portals left to right."""
    swaps = sorted((o.col, k) for o in level.objects
                   for k, v in O.GAMEMODE_PORTALS.items() if o.id == v)
    out, mode, i = {}, start_mode, 0
    for col in range(int(x0), int(x1) + 1):
        while i < len(swaps) and swaps[i][0] <= col:
            mode = swaps[i][1]
            i += 1
        out[col] = mode
    return out


def report(level: Level, t: Timeline, sections: dict[str, tuple[float, float]],
           rates=(60, 120, 240)) -> str:
    """Per-section table: song time, columns, speed, and frame-perfect spots per refresh."""
    modes = mode_map(level, 0, level.length)
    grid = occupancy(level)
    head = (f"{'section':<11}{'song time':>14}{'speed':>6}"
            + "".join(f"{f'{r}Hz spots/inputs':>18}" for r in rates))
    rows = [head, "-" * len(head)]
    totals = [[0, 0] for _ in rates]
    for name, (a, b) in sections.items():
        x0, x1 = t.col(t.bar(a)), t.col(t.bar(b))
        ta, tb = t.seconds(t.bar(a)), t.seconds(t.bar(b))
        measured = [spots(level, t, x0, x1, r, modes, grid) for r in rates]
        for total, (s, i) in zip(totals, measured):
            total[0] += s
            total[1] += i
        rows.append(
            f"{name:<11}{f'{int(ta//60)}:{ta%60:04.1f}-{int(tb//60)}:{tb%60:04.1f}':>14}"
            f"{t.speed_at(t.bar(a)):>6}"
            + "".join(f"{f'{s} / {i}':>18}" for s, i in measured))
    rows.append("-" * len(head))
    rows.append(f"{'total':<11}{'':>14}{'':>6}"
                + "".join(f"{f'{s} / {i}':>18}" for s, i in totals))
    return "\n".join(rows)
