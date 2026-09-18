"""Render levels so a human or Claude can check them without opening the game.

- `render_png` draws the level as stacked horizontal strips (gameplay objects only; deco is
  a faint outline) with column numbers every 10 blocks.
- `render_ascii` prints a character grid plus a list of portals and triggers in order.
"""
from __future__ import annotations

import base64
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import objects as O
from .level import GDObject, Level, UNIT

PX = 12                  # pixels per block
COLS_PER_STRIP = 100
MARGIN = 28

ORB_COLORS = {"yellow": "#ffe14d", "pink": "#ff7de0", "blue": "#4dc3ff", "green": "#4dff88",
              "red": "#ff5a4d", "black": "#1a1a1a", "dash_green": "#4dff88",
              "dash_pink": "#ff7de0"}
PORTAL_COLORS = {"cube": "#4dff88", "ship": "#ff7de0", "ball": "#ff5a4d", "ufo": "#ffb84d",
                 "wave": "#4dc3ff", "robot": "#e8e8e8", "spider": "#b84dff", "swing": "#ffe14d",
                 "gravity_down": "#4dc3ff", "gravity_up": "#ffe14d", "mirror": "#ffb84d",
                 "unmirror": "#4dc3ff", "normal_size": "#4dff88", "mini": "#ff7de0",
                 "dual": "#ffb84d", "single": "#4dc3ff"}
PORTAL_LABELS = {"gravity_down": "grav v", "gravity_up": "grav ^", "normal_size": "big",
                 "unmirror": "unmir"}
TRIGGER_COLORS = {"color": "#ffe14d", "move": "#4dc3ff", "alpha": "#b0b0b0", "toggle": "#ff5a4d",
                  "spawn": "#4dff88", "pulse": "#ff7de0", "rotate": "#ffb84d"}

_ORB_NAMES = {v: k for k, v in O.ORBS.items()}
_PAD_NAMES = {v: k for k, v in O.PADS.items()}
_PORTAL_NAMES = {v: k for k, v in O.PORTALS.items()}


def _flipped(o: GDObject) -> bool:
    return (str(o.get("5", "0")) == "1") != (float(o.get("6", 0)) % 360 == 180)


def _scale(o: GDObject) -> tuple[float, float]:
    base = float(o.get("32", 1))
    return float(o.get("128", base)), float(o.get("129", base))


def _trigger_kind(o: GDObject) -> str:
    return O.describe(o.id).removesuffix(" trigger")


def _row_range(objs: list[GDObject]) -> tuple[int, int]:
    rows = [o.gy / UNIT for o in objs if O.category(o.id) not in ("trigger", "deco")]
    top = max(rows, default=10)
    bottom = min(rows, default=0)
    return max(-1, math.floor(bottom) - 1), min(40, max(10, math.ceil(top) + 1))


def render_png(level: Level, path: str | Path, x0: float | None = None,
               x1: float | None = None) -> Path:
    objs = level.objects
    x0 = math.floor(x0 if x0 is not None else min((o.col for o in objs), default=0) - 5)
    x1 = math.ceil(x1 if x1 is not None else level.length + 4)
    r_lo, r_hi = _row_range([o for o in objs if x0 <= o.col <= x1])
    strip_h = (r_hi - r_lo + 2) * PX + 40
    n = max(1, math.ceil((x1 - x0) / COLS_PER_STRIP))
    width = COLS_PER_STRIP * PX + 2 * MARGIN
    img = Image.new("RGB", (width, n * strip_h + 26), "#101018")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    d.text((MARGIN, 6), f"{level.name}  -  {len(objs)} objects, ends ~col {level.length:.0f}",
           fill="#ffffff", font=font)

    for s in range(n):
        c0 = x0 + s * COLS_PER_STRIP
        c1 = c0 + COLS_PER_STRIP
        top = 26 + s * strip_h
        ground_y = top + (r_hi + 1) * PX

        def X(gx: float) -> float:
            return MARGIN + (gx / UNIT - c0) * PX

        def Y(gy: float) -> float:
            return ground_y - gy / UNIT * PX

        # background, ground, grid
        d.rectangle([MARGIN, top, MARGIN + COLS_PER_STRIP * PX, ground_y], fill="#1b1b2e")
        d.rectangle([MARGIN, ground_y, MARGIN + COLS_PER_STRIP * PX, top + (r_hi - r_lo + 1) * PX],
                    fill="#2b2b45")
        for c in range(c0, c1 + 1):
            gx = MARGIN + (c - c0) * PX
            strong = c % 10 == 0
            d.line([gx, top, gx, ground_y], fill="#34344f" if strong else "#222238")
            if strong:
                d.text((gx - 6, top + (r_hi - r_lo + 1) * PX + 2), str(c), fill="#9a9ab8",
                       font=font)
        for r in range(r_lo, r_hi + 1):
            yy = ground_y - r * PX
            d.line([MARGIN, yy, MARGIN + COLS_PER_STRIP * PX, yy],
                   fill="#34344f" if r % 5 == 0 else "#222238")
        d.line([MARGIN, ground_y, MARGIN + COLS_PER_STRIP * PX, ground_y], fill="#ffffff")

        lane_y = top + (r_hi - r_lo + 1) * PX + 24
        visible = [o for o in objs if c0 - 3 <= o.gx / UNIT <= c1 + 3]
        order = {"deco": 0, "text": 1, "solid": 2, "pad": 3, "hazard": 4, "saw": 4, "coin": 5,
                 "orb": 6, "startpos": 7, "portal": 8, "trigger": 9}
        for o in sorted(visible, key=lambda o: order[O.category(o.id)]):
            cat = O.category(o.id)
            cx, cy = X(o.gx), Y(o.gy)
            sx, sy = _scale(o)
            if cat == "trigger":
                if not (c0 <= o.gx / UNIT <= c1):
                    continue
                kind = _trigger_kind(o)
                col = TRIGGER_COLORS.get(kind, "#9a9ab8")
                d.polygon([(cx, lane_y - 5), (cx + 5, lane_y), (cx, lane_y + 5), (cx - 5, lane_y)],
                          fill=col)
                continue
            if not (r_lo - 1 <= o.gy / UNIT <= r_hi + 2):
                continue
            h = PX / 2
            if cat == "solid":
                if o.id == O.SLAB:
                    d.rectangle([cx - h * sx, cy - PX * 0.25, cx + h * sx, cy + PX * 0.25],
                                fill="#6a7fdb", outline="#c8d0ff")
                else:
                    d.rectangle([cx - h * sx, cy - h * sy, cx + h * sx, cy + h * sy],
                                fill="#4b5bb5", outline="#c8d0ff")
            elif cat == "hazard":
                hh = O.hazard_height(o.id) * PX * sy
                w = (h * 0.5 if o.id == O.SPIKE_TINY else h * 0.9) * sx
                off = O.SNAP_Y.get(o.id, 15) / UNIT * PX
                rot = float(o.get("6", 0)) % 360
                if rot in (90, 270):  # spike on a wall: point left/right
                    sign = 1 if rot == 90 else -1
                    base = cx - sign * h
                    d.polygon([(base, cy - w), (base, cy + w), (base + sign * hh, cy)], fill="#ff4d4d")
                elif _flipped(o):
                    base = cy - off
                    d.polygon([(cx - w, base), (cx + w, base), (cx, base + hh)], fill="#ff4d4d")
                else:
                    base = cy + off
                    d.polygon([(cx - w, base), (cx + w, base), (cx, base - hh)], fill="#ff4d4d")
            elif cat == "saw":
                rad = O.SAWS[o.id] * PX * sx
                d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline="#ff4d4d", width=2)
            elif cat == "orb":
                name = _ORB_NAMES[o.id]
                rad = PX * 0.4
                d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=ORB_COLORS[name],
                          outline="#ffffff")
                if name.startswith("dash"):
                    d.line([cx - rad, cy, cx + rad * 1.8, cy], fill="#ffffff", width=2)
            elif cat == "pad":
                name = _PAD_NAMES[o.id]
                if _flipped(o):
                    d.rectangle([cx - h * 0.8, cy - 1, cx + h * 0.8, cy + 3],
                                fill=ORB_COLORS[name])
                else:
                    d.rectangle([cx - h * 0.8, cy - 3, cx + h * 0.8, cy + 1],
                                fill=ORB_COLORS[name])
            elif cat == "portal":
                name = _PORTAL_NAMES[o.id]
                col = PORTAL_COLORS.get(name, "#ffffff")
                if name.endswith("x"):
                    d.polygon([(cx - 5, cy - PX), (cx + 6, cy), (cx - 5, cy + PX)], outline=col,
                              width=2)
                else:
                    d.rounded_rectangle([cx - 4, cy - PX * 1.45, cx + 4, cy + PX * 1.45], 3,
                                        outline=col, width=2)
                label = PORTAL_LABELS.get(name, name)
                d.text((cx - 3 * len(label), cy - PX * 1.45 - 12), label, fill=col, font=font)
            elif cat == "coin":
                d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill="#ffcc33", outline="#fff3b0")
            elif cat == "startpos":
                d.rectangle([cx - h, cy - h, cx + h, cy + h], outline="#4dff88", width=2)
                d.text((cx - 5, cy - 5), "SP", fill="#4dff88", font=font)
            elif cat == "text":
                try:
                    txt = base64.urlsafe_b64decode(str(o.get("31", "")) + "==").decode()
                except ValueError:
                    txt = "T"
                d.text((cx - 3 * len(txt[:24]), cy - 5), txt[:24], fill="#d0d0e0", font=font)
            else:
                d.rectangle([cx - h * sx, cy - h * sy, cx + h * sx, cy + h * sy],
                            outline="#3d3d5c")

        # clip anything that spilled past the strip's left/right edges
        area_bottom = top + (r_hi - r_lo + 1) * PX
        d.rectangle([0, top - 14, MARGIN - 1, area_bottom], fill="#101018")
        d.rectangle([MARGIN + COLS_PER_STRIP * PX + 1, top - 14, width, area_bottom],
                    fill="#101018")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def _cell_char(o: GDObject) -> str | None:
    cat = O.category(o.id)
    if cat == "solid":
        return "=" if o.id == O.SLAB else "#"
    if cat == "hazard":
        if o.id == O.SPIKE:
            return "v" if _flipped(o) else "^"
        return "'" if _flipped(o) else ","
    if cat == "saw":
        return "*"
    if cat == "orb":
        name = _ORB_NAMES[o.id]
        return "D" if name.startswith("dash") else {"black": "K"}.get(name, name[0].upper())
    if cat == "pad":
        return _PAD_NAMES[o.id][0]
    if cat == "coin":
        return "$"
    if cat == "startpos":
        return "S"
    if cat == "deco":
        return "."
    return None


_PRIORITY = "|DYPBGRK*^v,'ypbr$S#=."
LEGEND = ("legend: # block  = slab  ^ spike  v ceiling spike  , small spike  * saw  "
          "Y/P/B/G/R/K orb  D dash orb  y/p/b/r pad  | portal  $ coin  S start pos  . deco")


def render_ascii(level: Level, x0: float | None = None, x1: float | None = None,
                 width: int = 100) -> str:
    """Character map, `width` columns per band, plus an ordered list of portals/triggers.

    Legend: # block  = slab  ^ spike  v ceiling spike  , small spike  * saw
            Y P B G R K orbs (yellow pink blue green red black)  D dash orb
            y p b r pads  | portal  $ coin  S start pos  . deco
    """
    objs = level.objects
    x0 = math.floor(x0 if x0 is not None else min((o.col for o in objs), default=0))
    x1 = math.ceil(x1 if x1 is not None else level.length)
    inside = [o for o in objs if x0 - 0.5 <= o.col <= x1 + 0.5]
    r_lo, r_hi = _row_range(inside)
    r_lo = max(r_lo, 0)

    grid: dict[tuple[int, int], str] = {}

    def put(c: int, r: int, ch: str) -> None:
        old = grid.get((c, r))
        if old is None or _PRIORITY.index(ch) < _PRIORITY.index(old):
            grid[(c, r)] = ch

    events = []
    for o in inside:
        cat = O.category(o.id)
        c, r = math.floor(o.gx / UNIT), math.floor(o.gy / UNIT)
        if cat == "portal":
            for dr in (-1, 0, 1):
                put(c, r + dr, "|")
            events.append((o.gx, f"col {o.col:6.1f}  row {o.row:4.1f}  {O.describe(o.id)}"))
        elif cat == "trigger":
            detail = ""
            if o.id == O.COLOR_TRIGGER:
                detail = (f" ch {o.get('23', '?')} -> ({o.get('7', 0)},{o.get('8', 0)},"
                          f"{o.get('9', 0)}) over {o.get('10', 0)}s")
            elif o.id == O.MOVE_TRIGGER:
                dx, dy = float(o.get("28", 0)) / UNIT, float(o.get("29", 0)) / UNIT
                detail = f" group {o.get('51', '?')} by ({dx:g},{dy:g}) blocks in {o.get('10', 0)}s"
            elif "51" in o:
                detail = f" group {o.get('51')}"
            events.append((o.gx, f"col {o.col:6.1f}  {O.describe(o.id)}{detail}"))
        else:
            ch = _cell_char(o)
            if ch:
                put(c, r, ch)

    out = [LEGEND]
    for b0 in range(x0, x1 + 1, width):
        b1 = min(b0 + width - 1, x1)
        ruler = [" "] * (b1 - b0 + 1)
        for c in range(b0, b1 + 1):
            if c % 10 == 0:
                for i, ch in enumerate(str(c)):
                    if c - b0 + i < len(ruler):
                        ruler[c - b0 + i] = ch
        ruler = "".join(ruler)
        out.append("")
        out.append(f"cols {b0}-{b1}")
        out.append("     " + ruler)
        for r in range(r_hi, r_lo - 1, -1):
            line = "".join(grid.get((c, r), " ") for c in range(b0, b1 + 1))
            out.append(f"{r:>3}  {line.rstrip()}")
        out.append("     " + "~" * (b1 - b0 + 1))
    if events:
        out.append("")
        out.append("portals & triggers:")
        out.extend(text for _, text in sorted(events))
    return "\n".join(out)
