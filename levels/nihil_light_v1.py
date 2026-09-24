"""Nihil Light v1 - base layout.

Brief: top-50-extreme difficulty, memory based, tight gaps, nearly unreadable gameplay,
Artemis 13 / TS2 black-and-white deco (deco comes later), perfectly synced to
Silentroom - Nhelv (2020 remaster, 6:47). Parts the user describes in detail are marked
PLACEHOLDER and only get the right length, speed and gamemode for now.

Timing from tools/analyze_song.py on Downloads/Silentroom_-_Nhelv_(mp3.pm).mp3:
    175.186 BPM, first beat 0.401s, bar = 1.370s, 297 bars, 407.75s
This file runs 5s later than the user's own timestamps (their 2:33 = 2:38 here).

Song map (file time):
    0:06 intro | 0:26 main | 1:33 mid | 1:56 quiet | 2:04 loud | 2:38 EMPTY (Morse flash)
    2:48 build | 3:10 hit | 3:21 drop | 3:46 slow predrop (orb timing) | 4:05 RECALL
    4:29 flow | 5:11 late section | 6:41 fade

Headline mechanic (user's design): the cube flashes a randomised Morse sequence during the
empty part; from 4:05 the player replays it from memory - dot = up, dash = down, wrong
block = death, each jump a 60fps frame perfect - while the gameplay around it is already
hard. v1 lays out space, rhythm and difficulty curve; randomiser and death logic come next.
"""
import json
import math
from pathlib import Path

from gdmaker import Level
from gdmaker import patterns as P
from gdmaker.sync import Timeline

DRUMS = Path(__file__).resolve().parent.parent / "data" / "nhelv_drums.json"

BPM, OFFSET = 175.186, 0.401

# (start bar, end bar) snapped to bar lines from the section analysis
SECTIONS = {
    "lead_in":   (0, 4),        # 0:00-0:06  silence
    "intro":     (4, 19),       # 0:06-0:26  quiet intro
    "main_wave": (19, 35),      # 0:26-0:48
    "main_ship": (35, 52),      # 0:48-1:11
    "main_mini": (52, 68),      # 1:11-1:33
    "mid":       (68, 84),      # 1:33-1:56
    "quiet":     (84, 90),      # 1:56-2:04  breather
    "loud":      (90, 115),     # 2:04-2:38  dual
    "morse":     (115, 122),    # 2:38-2:48  PLACEHOLDER - Morse flashes
    "build":     (122, 138),    # 2:48-3:10
    "hit":       (138, 146),    # 3:10-3:21
    "drop":      (146, 165),    # 3:21-3:46
    "predrop":   (165, 178),    # 3:46-4:04  orb timing
    "recall":    (178, 196),    # 4:05-4:29  PLACEHOLDER - Morse recall, hard
    "flow":      (196, 227),    # 4:29-5:11  high intensity, 240Hz frame perfects
    "late":      (227, 292),    # 5:11-6:41
    "fade":      (292, 297),    # 6:41-6:47
}

SPEEDS = {19: "3x", 90: "4x", 115: "1x", 122: "3x", 138: "4x", 165: "3x", 196: "4x",
          227: "3x", 292: "2x"}

CH_WALL, CH_HAZARD, CH_HINT = 1, 2, 3

# Sections hand over along the ground (row ~1) so the next portal can't be missed.
LEAD, TAIL, HANDOVER_GAP = 10, 14, 2.6


def enter(lvl, x0: float, mode: str | None = None) -> int:
    if mode:
        lvl.portal(mode, round(x0) + 3, 1)
    return round(x0) + LEAD


def handover(lvl, x1: float, flying: bool = True) -> None:
    if flying:
        P.tunnel(lvl, round(x1) - TAIL, round(x1) - 1, 0.0, HANDOVER_GAP, wall=1, color=CH_WALL)


def beats(t: Timeline, bar0: float, bar1: float, per_bar: int):
    """Columns of every 1/per_bar note between two bars."""
    n = int(round((bar1 - bar0) * per_bar))
    return [t.col(t.bar(bar0) + i * 4.0 / per_bar) for i in range(n)]


def pinch_bars(lvl, t: Timeline, path, b0: float, b1: float, mode: str, *, step: float = 1.0,
               fps: int = 240, frames: float = 1.0, guard: float = 6) -> int:
    """Put a frame-perfect squeeze on bar lines through a range, sized from the speed that
    applies there, so each one measures `frames` frames at `fps` by construction."""
    made, bar = 0, math.ceil(b0)
    while bar < b1:
        x = round(t.col(t.bar(bar)))
        if t.col(t.bar(b0)) + guard <= x <= t.col(t.bar(b1)) - guard:
            P.pinch(lvl, x, path(x), mode, t.speed_at(t.bar(bar)), fps=fps, frames=frames,
                    width=2, wall=2, color=CH_HAZARD)
            made += 1
        bar += step
    return made


def build() -> Level:
    lvl = Level(
        "Nihil Light v1",
        description="Base layout. Memory extreme synced to Nhelv. WIP, by Claude.",
        custom_song=812038,          # the ID you map Nhelv onto in Jukebox
        speed="2x",
        bg=(6, 6, 8), ground=(10, 10, 12), line=(255, 255, 255), obj=(235, 235, 235),
    )
    lvl.color(CH_WALL, (20, 20, 22))
    lvl.color(CH_HAZARD, (245, 245, 245))
    lvl.color(CH_HINT, (110, 110, 115))

    t = Timeline(BPM, OFFSET, speed="2x")
    for bar, speed in SPEEDS.items():
        t.set_speed(t.bar(bar), speed)

    mem = P.Memory(lvl)
    for name, (a, b) in SECTIONS.items():
        globals()[f"section_{name}"](lvl, t, mem, t.col(t.bar(a)), t.col(t.bar(b)), a, b)

    t.place_portals(lvl)
    mem.arm(lvl)
    return lvl


# ---------------------------------------------------------------- sections

def section_lead_in(lvl, t, mem, x0, x1, b0, b1):
    """Silence. Nothing but the name."""
    lvl.text(x0 + 6, 6, "NIHIL LIGHT", scale=0.9, color=CH_HINT)


def section_intro(lvl, t, mem, x0, x1, b0, b1):
    """Cube, 2x. On-beat timings that tighten; one invisible spike states the theme."""
    start = enter(lvl, x0)
    for i, x in enumerate(beats(t, b0, b1, 2)):
        if not start <= x <= x1 - TAIL:
            continue
        if i % 4 == 3:
            lvl.spikes(round(x), 2, color=CH_HAZARD)
        elif i % 4 == 1:
            lvl.blocks(round(x), 0, 3, color=CH_WALL)
            lvl.spike(round(x) + 1, 1, color=CH_HAZARD)
        else:
            lvl.spike(round(x), color=CH_HAZARD)
    mem.hide(lvl.spike(round(t.col(t.bar(b1 - 2))), color=CH_HAZARD))


def section_main_wave(lvl, t, mem, x0, x1, b0, b1):
    """Wave, 3x. Zigzag corridor, one cycle per two beats, gap 2.6 -> 2.0."""
    start, end = enter(lvl, x0, "wave"), round(x1) - TAIL
    path = P.zigzag(start, t.blocks_per_beat(t.bar(b0)) * 2, 1.2, 6.2)
    for x in range(start, end):
        gap = 1.7 - 0.5 * (x - start) / max(1, end - start)   # 1.7 -> 1.2 blocks
        P.corridor(lvl, x, x, path, gap, wall=2, color=CH_WALL)
    handover(lvl, x1)


def section_main_ship(lvl, t, mem, x0, x1, b0, b1):
    """Ship, 3x. Straight-fly with gates alternating high/low on the beat."""
    start, end = enter(lvl, x0, "ship"), round(x1) - TAIL
    P.tunnel(lvl, start, end, 0.6, 5.4, wall=2, color=CH_WALL)
    for i, x in enumerate(beats(t, b0, b1, 4)):
        if not start + 6 <= x <= end - 6:
            continue
        low = 1.0 + (1.8 if i % 2 else 0.0)
        P.gate(lvl, round(x), low, low + 1.8, top=6, bottom=1, color=CH_WALL)
    handover(lvl, x1)


def section_main_mini(lvl, t, mem, x0, x1, b0, b1):
    """Mini wave, 3x. Twice the slope, so the corridor is steeper and the gap tighter."""
    start, end = enter(lvl, x0, "wave"), round(x1) - TAIL
    lvl.portal("mini", start - 4, 1)
    path = P.zigzag(start, t.blocks_per_beat(t.bar(b0)), 1.0, 5.0)
    for x in range(start, end):
        P.corridor(lvl, x, x, path, 1.15, wall=2, color=CH_WALL)   # mini: smaller hitbox
    lvl.portal("normal_size", end + 2, 1)
    handover(lvl, x1)


def drum_columns(t: Timeline, t0: float, t1: float) -> list[float]:
    """Columns of the drum hits between two song times (data/nhelv_drums.json, made by
    tools/analyze_song.py --onsets). Median gap is an 8th note: ~5 clicks a second."""
    times = json.loads(DRUMS.read_text())["times"]
    return [t.col_at_seconds(s) for s in times if t0 <= s <= t1]


def section_mid(lvl, t, mem, x0, x1, b0, b1):
    """1:33-1:56, 3x. Wave lead-in -> blue orb on every drum -> mode switch spam.

    1:43-1:49  the wave bounces between the corridor walls: one blue orb per drum hit,
               alternating high/low, 2.4 rows apart so a 45-degree wave can reach the next
               one in the 2.7 columns an 8th note gives it.
    1:49-1:56  same clicking, but the gamemode swaps every two hits as well.
    """
    start, end = enter(lvl, x0, "wave"), round(x1) - TAIL
    lead_end = round(t.col_at_seconds(103.0))      # 1:43
    spam_start = round(t.col_at_seconds(109.0))    # 1:49

    # lead-in: tight zigzag, no orbs yet
    path = P.zigzag(start, t.blocks_per_beat(t.bar(b0)) * 2, 1.2, 5.2)
    for x in range(start, lead_end):
        P.corridor(lvl, x, x, path, 1.4, wall=2, color=CH_WALL)

    # blue orb wave: a straight corridor, the orbs do all the work
    P.tunnel(lvl, lead_end, end, 2.6, 7.4, wall=2, color=CH_WALL)
    for i, x in enumerate(drum_columns(t, 103.0, 116.0)):
        if not lead_end <= x <= end - 2:
            continue
        lvl.orb("blue", round(x, 2), 3.8 if i % 2 else 6.2, color=CH_HAZARD)
        if x >= spam_start and i % 2 == 0:        # constant mode switching over the spam
            lvl.portal("ship" if (i // 2) % 2 else "wave", round(x, 2) + 1, 5)
    handover(lvl, x1)


def section_quiet(lvl, t, mem, x0, x1, b0, b1):
    """Breather before the dual. Cube, a few orbs, nothing cheap."""
    start = enter(lvl, x0, "cube")
    P.orb_chain(lvl, [x for x in beats(t, b0, b1, 4) if start <= x <= x1 - TAIL], 2.0)


def section_loud(lvl, t, mem, x0, x1, b0, b1):
    """4x dual ship. Symmetric walls: one input, two players, no room to read it."""
    lvl.portal("dual", round(x0) + 3, 1)
    start, end = enter(lvl, x0 + 3, "ship"), round(x1) - TAIL
    per_beat = t.blocks_per_beat(t.bar(b0))
    P.corridor(lvl, start, end, P.sine(start, per_beat * 4, 7.5, 9.5), 2.0, wall=1,
               floor=False, color=CH_WALL)
    P.corridor(lvl, start, end, P.sine(start, per_beat * 4, 0.5, 2.5, phase=0.5), 2.0,
               wall=1, ceiling=False, color=CH_WALL)
    lvl.portal("single", end + 3, 1)
    handover(lvl, x1)


def section_morse(lvl, t, mem, x0, x1, b0, b1):
    """PLACEHOLDER - the empty part (2:38-2:48, 7 bars at 1x).

    Design: cube on a flat safe floor with nothing to do; the cube/screen flashes a
    randomised Morse sequence on 8th notes. A random trigger picks the sequence and must
    also select the matching layout in section_recall. For now: safe floor + flash slots.
    """
    start = enter(lvl, x0, "cube")
    lvl.blocks(round(x0), 0, int(x1 - x0) + 4, color=CH_WALL)
    for i, x in enumerate(beats(t, b0, b1, 8)):
        if x >= start:
            lvl.text(round(x), 4, "." if i % 3 else "-", scale=0.35, color=CH_HINT)


def section_build(lvl, t, mem, x0, x1, b0, b1):
    """Wave, 3x. Rising and closing: 2.4 -> 1.6 straight into the hit."""
    start, end = enter(lvl, x0, "wave"), round(x1) - TAIL
    path = P.zigzag(start, t.blocks_per_beat(t.bar(b0)), 1.2, 5.2)
    for x in range(start, end):
        P.corridor(lvl, x, x, path, 1.5 - 0.4 * (x - start) / max(1, end - start), wall=2,
                   color=CH_WALL)  # 1.5 -> 1.1 into the hit
    handover(lvl, x1)


def section_hit(lvl, t, mem, x0, x1, b0, b1):
    """3:10. 4x ship bursts: short straight-flies separated by hard slams."""
    start, end = enter(lvl, x0, "ship"), round(x1) - TAIL
    P.tunnel(lvl, start, end, 0.6, 6.4, wall=1, color=CH_WALL)
    for i, x in enumerate(beats(t, b0, b1, 2)):
        if not start + 6 <= x <= end - 6:
            continue
        low = 1.2 if i % 2 else 3.6
        P.gate(lvl, round(x), low, low + 1.7, top=7, bottom=1, color=CH_WALL)
        P.gate(lvl, round(x) + 1, low, low + 1.7, top=7, bottom=1, color=CH_WALL)
    handover(lvl, x1)


def section_drop(lvl, t, mem, x0, x1, b0, b1):
    """3:21. 4x wave, the tightest sustained corridor in the level: 0.85 blocks (~1.3
    frames at 60Hz), with a 240Hz pinch dropped on every bar line."""
    start, end = enter(lvl, x0, "wave"), round(x1) - TAIL
    per_beat = t.blocks_per_beat(t.bar(b0))
    path = P.zigzag(start, per_beat * 1.0, 1.2, 6.0)
    for x in range(start, end):
        P.corridor(lvl, x, x, path, 0.67, wall=2, spikes=False, color=CH_WALL)
    pinch_bars(lvl, t, path, b0, b1, "wave", step=0.75)
    handover(lvl, x1)


def section_predrop(lvl, t, mem, x0, x1, b0, b1):
    """3:46 slow predrop -> pure orb timing (user's call).

    Cube over a pit: one orb per beat, so each click has to land on the beat or you fall.
    Orb heights drift with the melody line; the pit and ceiling spikes do the punishing.
    """
    start, end = enter(lvl, x0, "cube"), round(x1) - TAIL
    P.spike_teeth(lvl, range(start, end), 0, color=CH_HAZARD)          # the pit
    P.corridor(lvl, start, end, lambda _x: 7.5, 2.0, wall=1, floor=False, color=CH_WALL)
    line = P.sine(start, t.blocks_per_beat(t.bar(b0)) * 8, 2.5, 4.5)
    P.orb_chain(lvl, [x for x in beats(t, b0, b1, 4) if start <= x <= end], line)
    handover(lvl, x1, flying=False)


def section_recall(lvl, t, mem, x0, x1, b0, b1):
    """PLACEHOLDER - 4:05-4:29, the Morse recall (user's 4:00-4:24 + 5s).

    Design: the hard part and the memory test at once. One branch per beat: an upper and a
    lower landing; dot = up, dash = down; the random trigger that chose the flash sequence
    also arms the wrong landing as a death block. Every jump is meant to be a 60fps frame
    perfect, so landings are one block wide - exact gaps get tuned once you playtest.
    v1 places the rhythm and both branches so the shape is real and playable.
    """
    start, end = enter(lvl, x0, "cube"), round(x1) - TAIL
    for x in [x for x in beats(t, b0, b1, 4) if start <= x <= end - 6]:
        c = round(x)
        # "dot" = up: jump, the orb sits at the apex, it throws you onto the high platform
        lvl.orb("yellow", c, 2, color=CH_HAZARD)
        lvl.blocks(c + 1, 3, 3, color=CH_WALL)
        # "dash" = down: ignore the orb and stay on the ground, but still jump the spike
        lvl.spike(c + 4, 0, color=CH_HAZARD)
    handover(lvl, x1, flying=False)


def section_flow(lvl, t, mem, x0, x1, b0, b1):
    """4:29-5:11. High intensity flow at 4x, mode swapping every 4 bars.

    Two deliberate 240Hz frame perfects are marked FP below: a 1.2-gap wave pinch and a
    ship slam that only opens for a few pixels. Everything else is fast but readable-ish.
    """
    start, end = enter(lvl, x0, "wave"), round(x1) - TAIL
    per_beat = t.blocks_per_beat(t.bar(b0))
    quarter = (end - start) // 4
    edges = [start + i * quarter for i in range(4)] + [end]
    clear = 8                                        # blank columns around each mode swap

    # 1: wave at 0.8 blocks, with a 240Hz pinch every half bar
    path = P.zigzag(start, per_beat * 1.0, 1.2, 6.2)
    for x in range(edges[0], edges[1] - clear):
        P.corridor(lvl, x, x, path, 0.67, wall=2, spikes=False, color=CH_WALL)
    pinch_bars(lvl, t, path, b0, b0 + (b1 - b0) / 4, "wave", step=0.5)

    # 2: ship, second frame perfect - a slam that opens one block wide
    lvl.portal("ship", edges[1] - clear + 2, 1)
    P.tunnel(lvl, edges[1], edges[2] - clear, 0.6, 6.4, wall=1, color=CH_WALL)
    for i, x in enumerate(beats(t, b0 + (b1 - b0) / 4, b0 + (b1 - b0) / 2, 4)):
        if edges[1] + 4 <= x <= edges[2] - clear - 4:
            low = 1.2 if i % 2 else 3.8
            P.gate(lvl, round(x), low, low + 1.6, top=7, bottom=1, color=CH_WALL)
    fp2 = edges[1] + quarter // 2                                     # FP: ship slam
    P.pinch(lvl, fp2, 3.5, "ship", t.speed_at(t.bar(b0)), fps=240, frames=1.0,
            color=CH_HAZARD)

    # 3: spider, floor/ceiling teleports on the beat
    lvl.portal("spider", edges[2] - clear + 2, 1)
    P.tunnel(lvl, edges[2], edges[3] - clear, 0.0, 7.0, spikes=False, wall=1, floor=False,
             color=CH_WALL)
    for i, x in enumerate(beats(t, b0 + (b1 - b0) / 2, b0 + 3 * (b1 - b0) / 4, 4)):
        if edges[2] + 4 <= x <= edges[3] - clear - 4:
            lvl.spike(round(x), 6 if i % 2 else 0, ceiling=bool(i % 2), color=CH_HAZARD)

    # 4: wave again, fastest zigzag of the level, pinched every half bar
    lvl.portal("wave", edges[3] - clear + 2, 1)
    path2 = P.zigzag(edges[3], per_beat * 0.5, 1.2, 4.2)
    for x in range(edges[3], end):
        P.corridor(lvl, x, x, path2, 0.67, wall=2, spikes=False, color=CH_WALL)
    pinch_bars(lvl, t, path2, b0 + 3 * (b1 - b0) / 4, b1, "wave", step=0.5)
    handover(lvl, x1)


def section_late(lvl, t, mem, x0, x1, b0, b1):
    """5:11-6:41. The long tail: 3x, alternating wave and ship every 8 bars, one memory
    trap per phrase. Deliberately the least detailed section - it is the most likely to be
    rewritten once the front half plays well."""
    start, end = enter(lvl, x0, "wave"), round(x1) - TAIL
    per_beat = t.blocks_per_beat(t.bar(b0))
    phrase, clear = 8, 8
    x, bar, mode = start, b0, "wave"
    while x < end - clear:
        span = min(int(per_beat * 4 * phrase), end - x)
        stop = x + span - clear
        if mode == "wave":
            path = P.zigzag(x, per_beat * 2, 1.2, 6.0)
            for c in range(x, stop):
                P.corridor(lvl, c, c, path, 1.3, wall=1, color=CH_WALL)
            pinch_bars(lvl, t, path, bar, bar + phrase, "wave", step=phrase, guard=10)
            nxt = "ship"
        else:
            P.tunnel(lvl, x, stop, 0.8, 5.2, wall=1, color=CH_WALL)
            for i, c in enumerate(beats(t, bar, bar + phrase, 2)):
                if x + 6 <= c <= stop - 6:
                    low = 1.2 if i % 2 else 2.8
                    P.gate(lvl, round(c), low, low + 1.9, top=6, bottom=1, color=CH_WALL)
            nxt = "wave"
        if x + span < end - clear:
            lvl.portal(nxt, stop + 3, 1)
        x += span
        bar += phrase
        mode = nxt
    handover(lvl, x1)


def section_fade(lvl, t, mem, x0, x1, b0, b1):
    """6:41. Cube on flat ground, nothing left to do."""
    enter(lvl, x0, "cube")
    lvl.blocks(round(x0), 0, int(x1 - x0) + 12, color=CH_WALL)
    lvl.text(round(x1) - 6, 5, "nihil", scale=0.8, color=CH_HINT)
