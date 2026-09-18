"""Object IDs and placement data for GD 2.2.

Snap offsets were measured from real editor-placed objects in the user's save: most objects
sit at the centre of their grid cell (y = row*30 + 15), but pads and small spikes sit on the
cell floor. Anything not listed here is placed at the cell centre.

To learn an ID that isn't here: have the user place it in any level, then
`python gd.py show "<level>"` prints every object with its ID.
"""

# ---- solids
BLOCK = 1            # the classic outlined grid block
SLAB = 40            # half-height platform, sits in the top half of its cell

# ---- hazards
SPIKE = 8            # full spike (1 block)
SPIKE_MEDIUM = 103   # shorter spike
SPIKE_SHORT = 39     # flattest spike
SPIKE_TINY = 392     # half-width tiny spike

# ---- pads (sit on the floor of a cell)
PADS = {"yellow": 35, "pink": 140, "blue": 67, "red": 1332}

# ---- orbs
ORBS = {
    "yellow": 36, "pink": 141, "blue": 84, "green": 1022, "red": 1333, "black": 1330,
    "dash_green": 1704, "dash_pink": 1751,
}

# ---- portals
GAMEMODE_PORTALS = {
    "cube": 12, "ship": 13, "ball": 47, "ufo": 111, "wave": 660, "robot": 745,
    "spider": 1331, "swing": 1933,
}
SPEED_PORTALS = {"0.5x": 200, "1x": 201, "2x": 202, "3x": 203, "4x": 1334}
OTHER_PORTALS = {
    "gravity_down": 10, "gravity_up": 11,     # blue = normal, yellow = upside down
    "mirror": 45, "unmirror": 46,
    "normal_size": 99, "mini": 101,
    "dual": 286, "single": 287,
}
PORTALS = {**GAMEMODE_PORTALS, **SPEED_PORTALS, **OTHER_PORTALS}

# ---- misc
START_POS = 31
COIN = 1329
TEXT = 914

# ---- triggers
COLOR_TRIGGER = 899
MOVE_TRIGGER = 901
PULSE_TRIGGER = 1006
ALPHA_TRIGGER = 1007
TOGGLE_TRIGGER = 1049
SPAWN_TRIGGER = 1268
ROTATE_TRIGGER = 1346
LEGACY_BG_TRIGGER = 29
LEGACY_GROUND_TRIGGER = 30

# ---- color channels
BG, GROUND, LINE, CH_3DL, OBJ, P1, P2, GROUND2, MIDDLEGROUND, MIDDLEGROUND2 = (
    1000, 1001, 1002, 1003, 1004, 1005, 1006, 1009, 1013, 1014)

# ---- level settings enums
GAMEMODES = ["cube", "ship", "ball", "ufo", "wave", "robot", "spider", "swing"]  # kA2 index
SPEEDS = {"1x": 0, "0.5x": 1, "2x": 2, "3x": 3, "4x": 4}                         # kA4 value
SPEED_BLOCKS_PER_SECOND = {"0.5x": 8.372, "1x": 10.386, "2x": 12.914, "3x": 15.6, "4x": 19.2}

OFFICIAL_SONGS = [
    "Stereo Madness", "Back on Track", "Polargeist", "Dry Out", "Base After Base",
    "Can't Let Go", "Jumper", "Time Machine", "Cycles", "xStep", "Clutterfunk",
    "Theory of Everything", "Electroman Adventures", "Clubstep", "Electrodynamix",
    "Hexagon Force", "Blast Processing", "Theory of Everything 2", "Geometrical Dominator",
    "Deadlocked", "Fingerdash", "Dash",
]

EASING = {
    "none": 0, "ease_in_out": 1, "ease_in": 2, "ease_out": 3,
    "elastic_in_out": 4, "elastic_in": 5, "elastic_out": 6,
    "bounce_in_out": 7, "bounce_in": 8, "bounce_out": 9,
    "exp_in_out": 10, "exp_in": 11, "exp_out": 12,
    "sine_in_out": 13, "sine_in": 14, "sine_out": 15,
    "back_in_out": 16, "back_in": 17, "back_out": 18,
}

# y position of the object's centre above the floor of its grid cell (default 15 = centred)
SNAP_Y = {
    SPIKE_SHORT: 6, SPIKE_MEDIUM: 9, SPIKE_TINY: 5.25, SLAB: 23,
    35: 2, 140: 2, 67: 3, 1332: 2.5,
}

# objects the game gives extra default keys when placed in the editor
DEFAULT_KEYS = {oid: {"13": 1} for oid in SPEED_PORTALS.values()}
DEFAULT_KEYS[1331] = {"13": 1}

# ---- preview categories (only IDs we're sure of; everything else previews as deco)
_HAZARDS = {8: 1.0, 103: 0.6, 39: 0.4, 392: 0.35}   # spike -> height in blocks
SAWS = {88: 1.3, 89: 0.9, 98: 0.5}                   # saw -> radius in blocks
_ORB_IDS = {v: k for k, v in ORBS.items()}
_PAD_IDS = {v: k for k, v in PADS.items()}
_PORTAL_IDS = {v: k for k, v in PORTALS.items()}
_TRIGGER_NAMES = {
    COLOR_TRIGGER: "color", MOVE_TRIGGER: "move", PULSE_TRIGGER: "pulse",
    ALPHA_TRIGGER: "alpha", TOGGLE_TRIGGER: "toggle", SPAWN_TRIGGER: "spawn",
    ROTATE_TRIGGER: "rotate", LEGACY_BG_TRIGGER: "bg color", LEGACY_GROUND_TRIGGER: "ground color",
    1347: "follow", 1520: "shake", 1585: "animate", 1595: "touch", 1611: "count",
    1616: "stop", 1811: "instant count", 1812: "on death", 1814: "follow player y",
    1815: "collision", 1817: "pickup", 1912: "random", 1913: "camera zoom",
    1914: "static camera", 1916: "camera offset", 2015: "camera rotate", 2062: "camera edge",
}
_SOLID_IDS = {1, 2, 3, 4, 5, 6, 7, 40}


def category(obj_id: int) -> str:
    """Rough role of an object for previews: solid / hazard / saw / orb / pad / portal /
    trigger / startpos / coin / text / deco."""
    if obj_id in _HAZARDS:
        return "hazard"
    if obj_id in SAWS:
        return "saw"
    if obj_id in _ORB_IDS:
        return "orb"
    if obj_id in _PAD_IDS:
        return "pad"
    if obj_id in _PORTAL_IDS:
        return "portal"
    if obj_id in _TRIGGER_NAMES:
        return "trigger"
    if obj_id == START_POS:
        return "startpos"
    if obj_id == COIN:
        return "coin"
    if obj_id == TEXT:
        return "text"
    if obj_id in _SOLID_IDS:
        return "solid"
    return "deco"


def hazard_height(obj_id: int) -> float:
    return _HAZARDS.get(obj_id, 1.0)


def describe(obj_id: int) -> str:
    """Human name for an ID, e.g. 'ship portal', 'yellow orb', 'move trigger'."""
    if obj_id in _ORB_IDS:
        return f"{_ORB_IDS[obj_id]} orb"
    if obj_id in _PAD_IDS:
        return f"{_PAD_IDS[obj_id]} pad"
    if obj_id in _PORTAL_IDS:
        name = _PORTAL_IDS[obj_id]
        return f"{name} speed" if name.endswith("x") else f"{name} portal"
    if obj_id in _TRIGGER_NAMES:
        return f"{_TRIGGER_NAMES[obj_id]} trigger"
    named = {BLOCK: "block", SLAB: "slab", SPIKE: "spike", SPIKE_MEDIUM: "medium spike",
             SPIKE_SHORT: "short spike", SPIKE_TINY: "tiny spike", START_POS: "start pos",
             COIN: "user coin", TEXT: "text"}
    return named.get(obj_id, f"object {obj_id}")
