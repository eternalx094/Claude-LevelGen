"""Build GD levels in code.

Coordinates are in grid blocks: x = column (0 = where the player starts, grows to the right),
y = row above the ground (0 = the row sitting on the ground). Fractions are fine (x=10.5).
Internally GD uses units of 30 per block with object positions at their centres; `add`
does that conversion, including the per-object floor offsets GD's editor snaps to.
"""
from __future__ import annotations

import base64
from collections import Counter
from typing import Callable, Iterable
import xml.etree.ElementTree as ET

from . import objects as O
from .save import _el, decode_level_string, encode_level_string, player_name

UNIT = 30
RGB = tuple[int, int, int]

# Channel strings exactly as GD 2.2 writes them for a brand-new level.
_DEFAULT_CHANNELS = {
    1000: "1_40_2_125_3_255_11_255_12_255_13_255_4_-1_6_1000_7_1_15_1_18_0_8_1",
    1001: "1_0_2_102_3_255_11_255_12_255_13_255_4_-1_6_1001_7_1_15_1_18_0_8_1",
    1009: "1_0_2_102_3_255_11_255_12_255_13_255_4_-1_6_1009_7_1_15_1_18_0_8_1",
    1002: "1_255_2_255_3_255_11_255_12_255_13_255_4_-1_6_1002_5_1_7_1_15_1_18_0_8_1",
    1013: "1_40_2_125_3_255_11_255_12_255_13_255_4_-1_6_1013_7_1_15_1_18_0_8_1",
    1014: "1_40_2_125_3_255_11_255_12_255_13_255_4_-1_6_1014_7_1_15_1_18_0_8_1",
    1004: "1_255_2_255_3_255_11_255_12_255_13_255_4_-1_6_1004_7_1_15_1_18_0_8_1",
}

# Level settings (kA keys) in GD 2.2's order and defaults for a new level.
_DEFAULT_SETTINGS = [
    ("kA13", "0"), ("kA15", "0"), ("kA16", "0"), ("kA14", ""), ("kA6", "0"), ("kA7", "0"),
    ("kA25", "0"), ("kA17", "0"), ("kA18", "0"), ("kS39", "0"), ("kA2", "0"), ("kA3", "0"),
    ("kA8", "0"), ("kA4", "0"), ("kA9", "0"), ("kA10", "0"), ("kA22", "0"), ("kA23", "0"),
    ("kA24", "0"), ("kA27", "1"), ("kA40", "1"), ("kA48", "1"), ("kA41", "1"), ("kA42", "1"),
    ("kA28", "0"), ("kA29", "0"), ("kA31", "1"), ("kA32", "1"), ("kA36", "0"), ("kA43", "0"),
    ("kA44", "0"), ("kA45", "1"), ("kA46", "0"), ("kA47", "0"), ("kA33", "1"), ("kA34", "1"),
    ("kA35", "0"), ("kA37", "1"), ("kA38", "1"), ("kA39", "1"), ("kA19", "0"), ("kA26", "0"),
    ("kA20", "0"), ("kA21", "0"), ("kA11", "0"),
]
# The subset a start position carries (kA9=1 marks it as a start pos).
_START_POS_KEYS = [k for k, _ in _DEFAULT_SETTINGS[10:]]

# Objects GD itself gives these keys when placed in the editor.
_INTERACTIVE = set(O.ORBS.values()) | set(O.PADS.values()) | set(O.PORTALS.values()) | {
    O.START_POS, O.COIN}
_ORB_IDS = set(O.ORBS.values())


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return "0" if text == "-0" else text
    return str(value)


def _channel_string(channel: int, rgb: RGB, blending: bool, opacity: float) -> str:
    r, g, b = rgb
    blend = "_5_1" if blending else ""
    return f"1_{r}_2_{g}_3_{b}_6_{channel}{blend}_7_{_fmt(float(opacity))}_15_0_18_0_8_1"


def seconds_to_blocks(seconds: float, speed: str = "1x") -> float:
    """How far the player travels in `seconds` at a constant speed (for music sync)."""
    return seconds * O.SPEED_BLOCKS_PER_SECOND[speed]


class GDObject(dict):
    """One object: GD property key (as a string) -> value. '1' id, '2' x, '3' y (GD units).

    Objects parsed from an existing level remember their exact original text and write it
    back unchanged unless modified (real levels sometimes repeat a key within an object,
    which a dict would silently merge)."""

    _raw: str | None = None

    def __setitem__(self, key, value):
        self._raw = None
        super().__setitem__(key, value)

    def __delitem__(self, key):
        self._raw = None
        super().__delitem__(key)

    def update(self, *args, **kwargs):
        self._raw = None
        super().update(*args, **kwargs)

    def pop(self, *args):
        self._raw = None
        return super().pop(*args)

    def setdefault(self, key, default=None):
        if key not in self:
            self._raw = None
        return super().setdefault(key, default)

    @property
    def id(self) -> int:
        return int(self["1"])

    @property
    def gx(self) -> float:
        return float(self.get("2", 0))

    @property
    def gy(self) -> float:
        return float(self.get("3", 0))

    @property
    def col(self) -> float:
        """x in blocks (column the object's centre is in)."""
        return (self.gx - 15) / UNIT

    @property
    def row(self) -> float:
        """y in blocks, undoing the editor snap offset."""
        off = O.SNAP_Y.get(self.id, 15)
        if str(self.get("5", "0")) == "1":
            off = UNIT - off
        return (self.gy - off) / UNIT

    @property
    def groups(self) -> list[int]:
        raw = str(self.get("57", "")).strip(".")
        return [int(g) for g in raw.split(".") if g]

    def encode(self) -> str:
        if self._raw is not None:
            return self._raw
        return ",".join(f"{k},{_fmt(v)}" for k, v in self.items())

    @classmethod
    def parse(cls, text: str) -> "GDObject":
        parts = text.split(",")
        obj = cls(zip(parts[::2], parts[1::2]))
        obj._raw = text
        return obj


class Level:
    def __init__(
        self,
        name: str,
        *,
        description: str = "",
        song: int | str = 0,
        custom_song: int | None = None,
        gamemode: str = "cube",
        speed: str = "1x",
        mini: bool = False,
        dual: bool = False,
        flipped: bool = False,
        two_player: bool = False,
        bg: RGB | None = None,
        ground: RGB | None = None,
        ground2: RGB | None = None,
        line: RGB | None = None,
        obj: RGB | None = None,
        bg_texture: int = 0,
        ground_texture: int = 0,
        font: int = 0,
        song_offset: float = 0.0,
        fade_in: bool = False,
        fade_out: bool = False,
    ):
        if len(name) > 20:
            raise ValueError(f"GD level names are max 20 characters ({name!r} is {len(name)}).")
        if len(description) > 140:
            raise ValueError("GD descriptions are max 140 characters.")
        self.name = name
        self.description = description
        self.song = O.OFFICIAL_SONGS.index(song) if isinstance(song, str) else song
        self.custom_song = custom_song
        self.objects: list[GDObject] = []
        self.channels: dict[int, str] = dict(_DEFAULT_CHANNELS)
        self.settings = dict(_DEFAULT_SETTINGS)
        self.settings.update({
            "kA2": str(O.GAMEMODES.index(gamemode)), "kA4": str(O.SPEEDS[speed]),
            "kA3": _fmt(mini), "kA8": _fmt(dual), "kA11": _fmt(flipped),
            "kA10": _fmt(two_player), "kA6": str(bg_texture), "kA7": str(ground_texture),
            "kA18": str(font), "kA13": _fmt(float(song_offset)), "kA15": _fmt(fade_in),
            "kA16": _fmt(fade_out),
        })
        for channel, rgb in ((O.BG, bg), (O.GROUND, ground), (O.GROUND2, ground2),
                             (O.LINE, line), (O.OBJ, obj)):
            if rgb is not None:
                self.color(channel, rgb, blending=channel == O.LINE)
        self._header_raw: str | None = None  # set when loaded from an existing level
        self._next_group = 1

    # ------------------------------------------------------------ settings

    def color(self, channel: int, rgb: RGB, blending: bool = False, opacity: float = 1.0) -> int:
        """Set the starting colour of a channel (1-999 custom, or BG/GROUND/LINE/...)."""
        self.channels[channel] = _channel_string(channel, rgb, blending, opacity)
        return channel

    def new_group(self) -> int:
        used = {g for o in self.objects for g in o.groups}
        while self._next_group in used:
            self._next_group += 1
        self._next_group += 1
        return self._next_group - 1

    # ------------------------------------------------------------ placement

    def add(self, obj_id: int, x: float, y: float = 0, *, rotation: float = 0,
            flip_x: bool = False, flip_y: bool = False, scale: float | tuple | None = None,
            color: int | None = None, detail_color: int | None = None,
            groups: Iterable[int] | None = None, z_layer: int | None = None,
            z_order: int | None = None, editor_layer: int | None = None,
            dont_fade: bool = False, dont_enter: bool = False, snap: bool = True,
            raw: dict | None = None) -> GDObject:
        """Place any object by ID at grid position (x, y). `raw` sets GD keys directly,
        e.g. raw={"10": 0.5} (keys can be ints or strings)."""
        off = 15.0
        if snap and rotation % 360 in (0, 180):
            off = O.SNAP_Y.get(obj_id, 15)
            if flip_y != (rotation % 360 == 180):
                off = UNIT - off
        o = GDObject({"1": obj_id, "2": float(x * UNIT + 15), "3": float(y * UNIT + off)})
        if flip_x:
            o["4"] = 1
        if flip_y:
            o["5"] = 1
        if rotation:
            o["6"] = rotation
        if scale is not None:
            sx, sy = scale if isinstance(scale, tuple) else (scale, scale)
            o["128"], o["129"] = sx, sy
        if editor_layer is not None:
            o["20"] = editor_layer
        if color is not None:
            o["21"] = color
        if detail_color is not None:
            o["22"] = detail_color
        if z_layer is not None:
            o["24"] = z_layer
        if z_order is not None:
            o["25"] = z_order
        if groups:
            o["57"] = ".".join(str(g) for g in groups)
        if dont_fade:
            o["64"] = 1
        if dont_enter:
            o["67"] = 1
        if obj_id in _ORB_IDS:
            o["11"] = 1
        for k, v in O.DEFAULT_KEYS.get(obj_id, {}).items():
            o[k] = v
        if obj_id in _INTERACTIVE:
            o["36"] = 1
        for k, v in (raw or {}).items():
            o[str(k)] = v
        self.objects.append(o)
        return o

    def block(self, x: float, y: float = 0, **kw) -> GDObject:
        return self.add(O.BLOCK, x, y, **kw)

    def blocks(self, x: float, y: float = 0, length: int = 1, **kw) -> list[GDObject]:
        """A horizontal run of `length` blocks starting at column x."""
        return [self.add(O.BLOCK, x + i, y, **kw) for i in range(length)]

    def column(self, x: float, y: float = 0, height: int = 1, **kw) -> list[GDObject]:
        """A vertical stack of `height` blocks going up from row y."""
        return [self.add(O.BLOCK, x, y + i, **kw) for i in range(height)]

    def fill(self, x0: float, y0: float, x1: float, y1: float, obj_id: int = O.BLOCK,
             **kw) -> list[GDObject]:
        """Rectangle of objects, corners inclusive."""
        return [self.add(obj_id, x0 + i, y0 + j, **kw)
                for i in range(int(x1 - x0) + 1) for j in range(int(y1 - y0) + 1)]

    def slab(self, x: float, y: float = 0, length: int = 1, **kw) -> list[GDObject]:
        """Thin platforms occupying the top half of row y (standing height = top of row y)."""
        return [self.add(O.SLAB, x + i, y, **kw) for i in range(length)]

    _SPIKE_SIZES = {"full": O.SPIKE, "medium": O.SPIKE_MEDIUM, "short": O.SPIKE_SHORT,
                    "tiny": O.SPIKE_TINY}

    def spike(self, x: float, y: float = 0, *, size: str = "full", ceiling: bool = False,
              **kw) -> GDObject:
        """A spike in cell (x, y). ceiling=True hangs it upside down from the top of the cell."""
        return self.add(self._SPIKE_SIZES[size], x, y, flip_y=ceiling, **kw)

    def spikes(self, x: float, count: int = 1, y: float = 0, **kw) -> list[GDObject]:
        return [self.spike(x + i, y, **kw) for i in range(count)]

    def orb(self, kind: str, x: float, y: float, **kw) -> GDObject:
        return self.add(O.ORBS[kind], x, y, **kw)

    def pad(self, kind: str, x: float, y: float = 0, *, ceiling: bool = False, **kw) -> GDObject:
        return self.add(O.PADS[kind], x, y, flip_y=ceiling, **kw)

    def portal(self, kind: str, x: float, y: float = 1, **kw) -> GDObject:
        """Gamemode ('ship', 'wave', ...), speed ('2x'), 'gravity_up'/'gravity_down',
        'mirror'/'unmirror', 'mini'/'normal_size', 'dual'/'single'. Portals are ~3 blocks
        tall and centred on row y, so y=1 catches a player running along the ground."""
        return self.add(O.PORTALS[kind], x, y, **kw)

    def speed(self, value: str, x: float, y: float = 1, **kw) -> GDObject:
        return self.add(O.SPEED_PORTALS[value], x, y, **kw)

    def coin(self, x: float, y: float, **kw) -> GDObject:
        return self.add(O.COIN, x, y, **kw)

    def text(self, x: float, y: float, text: str, scale: float = 0.5, **kw) -> GDObject:
        encoded = base64.urlsafe_b64encode(text.encode()).decode()
        return self.add(O.TEXT, x, y, scale=scale, raw={"31": encoded, **kw.pop("raw", {})}, **kw)

    def start_pos(self, x: float, y: float = 0, *, gamemode: str = "cube", speed: str = "1x",
                  mini: bool = False, dual: bool = False, flipped: bool = False) -> GDObject:
        """Practice/testing checkpoint. The editor's 'play from start pos' uses it."""
        values = {k: v for k, v in _DEFAULT_SETTINGS if k in _START_POS_KEYS}
        values.update({"kA2": O.GAMEMODES.index(gamemode), "kA4": O.SPEEDS[speed],
                       "kA3": _fmt(mini), "kA8": _fmt(dual), "kA9": 1, "kA11": _fmt(flipped)})
        return self.add(O.START_POS, x, y, raw=values)

    # ------------------------------------------------------------ triggers
    # Triggers fire when the player's x passes them (unless touch/spawn triggered), so
    # only x matters. They default to row -3, tucked under the ground in the editor.

    def trigger(self, obj_id: int, x: float, y: float = -3, *, touch: bool = False,
                spawn: bool = False, multi: bool = False, groups: Iterable[int] | None = None,
                raw: dict | None = None) -> GDObject:
        keys: dict = {"36": 1}
        if touch:
            keys["11"] = 1
        if spawn:
            keys["62"] = 1
        if multi:
            keys["87"] = 1
        keys.update({str(k): v for k, v in (raw or {}).items()})
        return self.add(obj_id, x, y, groups=groups, raw=keys)

    def color_trigger(self, x: float, channel: int, rgb: RGB, duration: float = 0.5, *,
                      opacity: float = 1.0, blending: bool = False, **kw) -> GDObject:
        r, g, b = rgb
        raw = {"7": r, "8": g, "9": b, "10": float(duration), "35": float(opacity), "23": channel}
        if blending:
            raw["17"] = 1
        return self.trigger(O.COLOR_TRIGGER, x, raw=raw, **kw)

    def move(self, x: float, group: int, dx: float = 0, dy: float = 0, duration: float = 0.5,
             easing: str = "none", *, lock_player_x: bool = False, **kw) -> GDObject:
        """Move a group by (dx, dy) BLOCKS. Stored in GD units (30 per block); the editor
        UI shows these values divided by 3 (10 per block)."""
        raw = {"51": group, "28": float(dx * UNIT), "29": float(dy * UNIT),
               "10": float(duration), "30": O.EASING[easing], "85": 2}
        if lock_player_x:
            raw["58"] = 1
        return self.trigger(O.MOVE_TRIGGER, x, raw=raw, **kw)

    def alpha(self, x: float, group: int, opacity: float, duration: float = 0.0,
              **kw) -> GDObject:
        return self.trigger(O.ALPHA_TRIGGER, x,
                            raw={"51": group, "10": float(duration), "35": float(opacity)}, **kw)

    def toggle(self, x: float, group: int, on: bool, **kw) -> GDObject:
        raw = {"51": group}
        if on:
            raw["56"] = 1
        return self.trigger(O.TOGGLE_TRIGGER, x, raw=raw, **kw)

    def spawn(self, x: float, group: int, delay: float = 0.0, **kw) -> GDObject:
        return self.trigger(O.SPAWN_TRIGGER, x, raw={"51": group, "63": float(delay)}, **kw)

    # ------------------------------------------------------------ editing

    def where(self, pred: Callable[[GDObject], bool]) -> list[GDObject]:
        return [o for o in self.objects if pred(o)]

    def between(self, x0: float, x1: float) -> list[GDObject]:
        """Objects whose centre column is in [x0, x1]."""
        return self.where(lambda o: x0 - 0.01 <= o.col <= x1 + 0.01)

    def remove(self, pred: Callable[[GDObject], bool]) -> int:
        before = len(self.objects)
        self.objects = [o for o in self.objects if not pred(o)]
        return before - len(self.objects)

    def clear(self, x0: float, x1: float, *, keep_triggers: bool = True) -> int:
        """Delete everything with its centre in columns [x0, x1]."""
        def doomed(o: GDObject) -> bool:
            if keep_triggers and O.category(o.id) == "trigger":
                return False
            return x0 - 0.01 <= o.col <= x1 + 0.01
        return self.remove(doomed)

    def shift(self, from_x: float, by: float) -> None:
        """Push every object at column >= from_x right by `by` blocks (negative pulls left).
        Use it to lengthen or shorten a section without redoing what comes after."""
        for o in self.objects:
            if o.col >= from_x - 0.01:
                o["2"] = o.gx + by * UNIT

    # ------------------------------------------------------------ output

    @property
    def length(self) -> float:
        """Column of the right-most object (roughly where the level ends)."""
        return max((o.col for o in self.objects), default=0.0)

    def col_at_percent(self, percent: float) -> float:
        """Approximate column for a death/progress percentage the player reports."""
        return self.length * percent / 100

    def header(self) -> str:
        if self._header_raw is not None:
            return self._header_raw
        channels = "|".join(self.channels.values()) + "|"
        settings = ",".join(f"{k},{v}" for k, v in self.settings.items())
        return f"kS38,{channels},{settings}"

    def level_string(self) -> str:
        if self._header_raw == "" and not self.objects:
            return ""  # a level that was never opened in the editor has no data at all
        body = "".join(o.encode() + ";" for o in self.objects)
        return f"{self.header()};{body}"

    def to_entry(self, creator: str | None = None, binary_version: int = 47) -> ET.Element:
        """The <d> element GD stores for a level in CCLocalLevels.dat."""
        d = ET.Element("d")

        def put(key: str, tag: str, text: str | None = None) -> None:
            d.append(_el("k", key))
            d.append(_el(tag, text))

        put("kCEK", "i", "4")
        put("k2", "s", self.name)
        if self.description:
            put("k3", "s", base64.urlsafe_b64encode(self.description.encode()).decode())
        put("k4", "s", encode_level_string(self.level_string()))
        put("k5", "s", creator or player_name())
        if self.custom_song:
            put("k45", "i", str(self.custom_song))
        elif self.song:
            put("k8", "i", str(self.song))
        put("k13", "t")
        put("k21", "i", "2")
        put("k16", "i", "1")
        put("k50", "i", str(binary_version))
        put("k48", "i", str(len(self.objects)))
        put("kI1", "r", "0")
        put("kI2", "r", "90")
        put("kI3", "r", "1")
        kI6 = ET.Element("d")
        for i in range(14):
            kI6.append(_el("k", str(i)))
            kI6.append(_el("s", "0"))
        d.append(_el("k", "kI6"))
        d.append(kI6)
        return d

    @classmethod
    def from_level_string(cls, name: str, level_string: str) -> "Level":
        """Load an existing level for editing. Its header (colours, settings) is kept as-is."""
        header, _, body = level_string.partition(";")
        lvl = cls(name[:20])
        lvl._header_raw = header
        parts = header.split(",")
        lvl.settings.update({k: v for k, v in zip(parts[::2], parts[1::2]) if k.startswith("kA")})
        lvl.objects = [GDObject.parse(t) for t in body.split(";") if t.strip()]
        return lvl

    @classmethod
    def from_entry(cls, entry: ET.Element) -> "Level":
        from .save import entry_get
        return cls.from_level_string(entry_get(entry, "k2") or "Unnamed",
                                     decode_level_string(entry_get(entry, "k4") or ""))

    # ------------------------------------------------------------ sanity checks

    def mode_at(self, col: float) -> tuple[str, str]:
        """(gamemode, speed) the player has at a column, following portals left to right."""
        mode = O.GAMEMODES[int(self.settings.get("kA2") or 0)]
        speeds = {v: k for k, v in O.SPEEDS.items()}
        speed = speeds.get(int(self.settings.get("kA4") or 0), "1x")
        gm = {v: k for k, v in O.GAMEMODE_PORTALS.items()}
        sp = {v: k for k, v in O.SPEED_PORTALS.items()}
        for o in sorted(self.objects, key=lambda o: o.gx):
            if o.col > col:
                break
            if o.id in gm:
                mode = gm[o.id]
            elif o.id in sp:
                speed = sp[o.id]
        return mode, speed

    def lint(self) -> list[str]:
        """Cheap checks for the mistakes that make generated levels unfair or broken."""
        warnings = []
        dupes = Counter(o.encode() for o in self.objects)
        for text, n in dupes.items():
            if n > 1:
                o = GDObject.parse(text)
                warnings.append(f"{n}x identical {O.describe(o.id)} at col {o.col:g} row {o.row:g}")

        hazards = [o for o in self.objects if O.category(o.id) in ("hazard", "saw")]
        for o in hazards:
            if o.col < 6:
                warnings.append(f"{O.describe(o.id)} at col {o.col:g}: too close to the start")

        portals = [o for o in self.objects if o.id in O.GAMEMODE_PORTALS.values()]
        for p in portals:
            # only hazards roughly in front of the player, not corridor walls above/below
            near = [h for h in hazards
                    if p.col < h.col < p.col + 2.5 and abs(h.row - p.row) <= 1.5]
            if near:
                warnings.append(f"hazard {near[0].col - p.col:.1f} blocks after the "
                                f"{O.describe(p.id)} at col {p.col:g} (give ~3+ blocks)")

        # runs of floor spikes in cube mode: >3 full spikes in a row can't be jumped
        # unless an orb or pad right before/over them gives the extra height
        floor = sorted({round(o.col) for o in hazards
                        if o.id == O.SPIKE and abs(o.row) < 0.01 and "5" not in o})
        boosts = [o.col for o in self.objects if O.category(o.id) in ("orb", "pad")]
        run = []
        for c in floor + [None]:
            if run and (c is None or c != run[-1] + 1):
                mode, speed = self.mode_at(run[0])
                boosted = any(run[0] - 3 <= b <= run[-1] for b in boosts)
                if (len(run) > 3 and not boosted and mode in ("cube", "robot")
                        and speed in ("0.5x", "1x")):
                    warnings.append(f"{len(run)} floor spikes in a row at cols {run[0]}-{run[-1]} "
                                    f"({mode}, {speed}): more than a triple is impossible")
                run = []
            if c is not None:
                run.append(c)
        return warnings
