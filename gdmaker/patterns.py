"""Reusable building blocks for hard levels: spike-lined corridors, zigzag paths, spam
tunnels, timing chains and memory (invisible) objects.

A "path" is just a function column -> centre row. Build one with `waypoints`, `zigzag` or
`sine`, then hand it to `corridor`, which lines both sides with spikes and packs blocks
behind them - the snaking spike tunnels extreme demons are made of.

Gap sizes (corridor height in blocks), rough guide:
    3.0+  comfortable     2.2  hard      1.8  extreme      1.4  frame-perfect nonsense
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Sequence

from . import objects as O
from .level import GDObject, Level

Path = Callable[[float], float]


# ---------------------------------------------------------------- paths

def waypoints(points: Sequence[tuple[float, float]]) -> Path:
    """Straight lines through (column, row) points; flat outside the range."""
    pts = sorted(points)

    def path(x: float) -> float:
        if x <= pts[0][0]:
            return pts[0][1]
        if x >= pts[-1][0]:
            return pts[-1][1]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 <= x <= x1:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 > x0 else y1
        return pts[-1][1]
    return path


def zigzag(x0: float, period: float, low: float, high: float, phase: float = 0.0) -> Path:
    """Triangle wave - the shape a wave section wants. `period` is columns per full cycle."""
    def path(x: float) -> float:
        u = ((x - x0) / period + phase) % 1.0
        return low + (high - low) * (2 * u if u < 0.5 else 2 * (1 - u))
    return path


def sine(x0: float, period: float, low: float, high: float, phase: float = 0.0) -> Path:
    mid, amp = (low + high) / 2, (high - low) / 2

    def path(x: float) -> float:
        return mid + amp * math.sin(2 * math.pi * ((x - x0) / period + phase))
    return path


def offset(path: Path, dy: float) -> Path:
    return lambda x: path(x) + dy


# ---------------------------------------------------------------- structures

SEAL_TOP = 14.0    # corridors are sealed to here, so nothing can be flown around


def corridor(lvl: Level, x0: float, x1: float, path: Path, gap: float, *, step: float = 1.0,
             wall: int = 2, spikes: bool = True, floor: bool = True, ceiling: bool = True,
             color: int | None = None, groups: Iterable[int] | None = None,
             clamp_low: float | None = 0.0, seal: bool = True) -> list[GDObject]:
    """Line a path with spike-tipped walls above and below, `gap` blocks apart.

    `wall` is how many blocks of filler sit behind each spike row (the visual mass).
    `seal` closes the rest of the column with one stretched block per side, so the player
    cannot simply fly under or over the corridor - without it a rising corridor leaves an
    open channel along the ground. `clamp_low` stops the lower wall going below the ground.
    """
    made: list[GDObject] = []
    x = x0
    while x <= x1 + 1e-9:
        centre = path(x)
        low = centre - gap / 2      # where the floor spikes' tips reach
        high = centre + gap / 2     # where the ceiling spikes' tips reach
        # walls sit at the exact fractional height, so `gap` is the real passage
        if floor:
            if spikes and (clamp_low is None or low - 1 >= clamp_low):
                made.append(lvl.spike(x, low - 1, color=color, groups=groups))
            for i in range(1, wall + 1):
                row = low - 1 - i
                if clamp_low is None or row >= clamp_low - 0.5:
                    made.append(lvl.block(x, row, color=color, groups=groups))
        if ceiling:
            if spikes:
                made.append(lvl.spike(x, high, ceiling=True, color=color, groups=groups))
            for i in range(1, wall + 1):
                made.append(lvl.block(x, high + i, color=color, groups=groups))
        if seal:
            if floor:
                bottom = low - 1 - wall          # everything below the built wall
                if bottom > 0.05:
                    made.append(lvl.add(O.BLOCK, x, bottom / 2 - 0.5, scale=(1, bottom),
                                        color=color, groups=groups))
            if ceiling:
                top = high + 1 + wall            # everything above it
                if SEAL_TOP - top > 0.05:
                    height = SEAL_TOP - top
                    made.append(lvl.add(O.BLOCK, x, (top + SEAL_TOP) / 2 - 0.5,
                                        scale=(1, height), color=color, groups=groups))
        x += step
    return made


def frame_gap(mode: str, speed: str, fps: int = 240, frames: float = 1.0) -> float:
    """The passage height whose input window is exactly `frames` frames at `fps`.

    wave at 4x: 0.43 blocks for one 240Hz frame, 0.67 for one 60Hz frame.
    Use it to place a pinch that is frame perfect by construction rather than by feel.
    """
    from .difficulty import HITBOX
    return HITBOX.get(mode, 1.0) + frames * O.SPEED_BLOCKS_PER_SECOND[speed] / fps


def pinch(lvl: Level, x: float, centre: float, mode: str, speed: str, *, fps: int = 240,
          frames: float = 1.0, width: int = 2, wall: int = 2, color: int | None = None
          ) -> list[GDObject]:
    """A deliberate frame-perfect squeeze `width` columns long, centred on a row.

    Built from blocks, not spikes: a spike's hitbox is ~0.6 of its cell, so spike-lined
    walls leave ~0.4 blocks more passage than the tip-to-tip gap suggests - fine for normal
    corridors, useless when the whole window is 0.43 blocks wide.
    """
    gap = frame_gap(mode, speed, fps, frames)
    return corridor(lvl, x, x + width - 1, lambda _x: centre, gap, wall=wall, spikes=False,
                    color=color)


def tunnel(lvl: Level, x0: float, x1: float, low: float, high: float, **kw) -> list[GDObject]:
    """Straight corridor between two rows (straight-fly ship, wave tunnel)."""
    centre, gap = (low + high) / 2, high - low
    return corridor(lvl, x0, x1, lambda _x: centre, gap, **kw)


def gate(lvl: Level, x: float, open_low: float, open_high: float, *, top: float = 12,
         bottom: float = 0, color: int | None = None, groups: Iterable[int] | None = None,
         spikes: bool = True) -> list[GDObject]:
    """A wall with one window open - the classic wave/ship gate."""
    made = []
    for row in range(int(bottom), int(math.floor(open_low))):
        made.append(lvl.block(x, row, color=color, groups=groups))
    for row in range(int(math.ceil(open_high)) + 1, int(top) + 1):
        made.append(lvl.block(x, row, color=color, groups=groups))
    if spikes:
        if open_low - 1 >= bottom:
            made.append(lvl.spike(x, math.floor(open_low) - 1, color=color, groups=groups))
        made.append(lvl.spike(x, math.ceil(open_high), ceiling=True, color=color, groups=groups))
    return made


def spike_teeth(lvl: Level, xs: Iterable[float], row: float = 0, *, ceiling: bool = False,
                size: str = "full", **kw) -> list[GDObject]:
    """Individual hazards at given columns - cube timing patterns."""
    return [lvl.spike(x, row, size=size, ceiling=ceiling, **kw) for x in xs]


def orb_chain(lvl: Level, xs: Iterable[float], row: float | Callable[[float], float],
              kind: str = "yellow", **kw) -> list[GDObject]:
    """Orbs at given columns; `row` may be a constant or a path."""
    out = []
    for x in xs:
        y = row(x) if callable(row) else row
        out.append(lvl.orb(kind, x, y, **kw))
    return out


def pillars(lvl: Level, xs: Iterable[float], height: int, *, from_ceiling: bool = False,
            ceiling_row: float = 12, tip_spike: bool = True, **kw) -> list[GDObject]:
    """Columns of blocks growing from the floor (or hanging from `ceiling_row`)."""
    made = []
    for x in xs:
        if from_ceiling:
            for i in range(height):
                made.append(lvl.block(x, ceiling_row - i, **kw))
            if tip_spike:
                made.append(lvl.spike(x, ceiling_row - height, ceiling=True, **kw))
        else:
            for i in range(height):
                made.append(lvl.block(x, i, **kw))
            if tip_spike:
                made.append(lvl.spike(x, height, **kw))
    return made


# ---------------------------------------------------------------- memory / readability

class Memory:
    """Objects that are invisible while still being solid or deadly.

    One alpha trigger at the very start of the level hides every object handed to `hide`,
    so the player has to know they are there. Call `arm(lvl)` once, after building.

        mem = Memory(lvl)
        mem.hide(lvl.spike(120, 0))          # an invisible spike
        mem.hide(corridor(lvl, 200, 260, p, 2.0))
        mem.arm(lvl)
    """

    def __init__(self, lvl: Level, group: int | None = None):
        self.group = group or lvl.new_group()
        self.count = 0

    def hide(self, obj: GDObject | Iterable[GDObject]) -> GDObject | Iterable[GDObject]:
        items = [obj] if isinstance(obj, dict) else list(obj)
        for o in items:
            o["57"] = ".".join(str(g) for g in (*o.groups, self.group))
        self.count += len(items)
        return obj

    def arm(self, lvl: Level, x: float = -8) -> GDObject:
        """Hide everything collected. Put this before the player's start column."""
        return lvl.alpha(x, self.group, opacity=0.0, duration=0.0)


def fade_in(lvl: Level, objs: Iterable[GDObject], at_col: float, duration: float = 0.3,
            group: int | None = None) -> int:
    """Keep objects invisible until a column, then fade them in (reveal tricks)."""
    group = group or lvl.new_group()
    for o in objs:
        o["57"] = ".".join(str(g) for g in (*o.groups, group))
    lvl.alpha(-8, group, opacity=0.0, duration=0.0)
    lvl.alpha(at_col, group, opacity=1.0, duration=duration)
    return group
