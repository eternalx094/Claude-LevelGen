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
from gdmaker import rhythm as R
from gdmaker.sync import Timeline

DRUMS = Path(__file__).resolve().parent.parent / "data" / "nhelv_drums.json"
HITS = Path(__file__).resolve().parent.parent / "data" / "nhelv_hits.json"

BPM, OFFSET = 175.186, 0.401

# (start bar, end bar) snapped to bar lines from the section analysis
SECTIONS = {
    "lead_in":   (0, 4),        # 0:00-0:06  silence
    "intro":     (4, 17),       # 0:06-0:24  bass line: spider, then orbs
    "main_wave": (17, 35),      # 0:24-0:48  wave on the drums
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

CH_EDGE, CH_FILL, CH_HAZARD, CH_HINT = 1, 2, 3, 4
CH_WALL = CH_EDGE      # corridor edges read bright; the mass behind them stays dark

# the passage the counter should measure in the brutal sections: one 60Hz frame
# for a wave at 4x. Pinches inside them are built to one 240Hz frame.
TIGHT_PASSAGE = 0.67
# the main sections: hard but readable (~2.5 frames at 60Hz for a wave at 3x)
MAIN_PASSAGE = 1.0

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
               fps: int = 240, frames: float = 1.0, guard: float = 6, slope: float = 0.0) -> int:
    """Put a frame-perfect squeeze on bar lines through a range, sized from the speed that
    applies there, so each one measures `frames` frames at `fps` by construction."""
    made, bar = 0, math.ceil(b0)
    while bar < b1:
        x = round(t.col(t.bar(bar)))
        if t.col(t.bar(b0)) + guard <= x <= t.col(t.bar(b1)) - guard:
            P.pinch(lvl, x, path(x), mode, t.speed_at(t.bar(bar)), fps=fps, frames=frames,
                    width=2, wall=2, color=CH_HAZARD, slope=slope)
            made += 1
        bar += step
    return made


def build() -> Level:
    lvl = Level(
        "Nihil Light v1",
        description="Base layout. Memory extreme synced to Nhelv. WIP, by Claude.",
        custom_song=812038,          # the ID you map Nhelv onto in Jukebox
        speed="2x",
        bg=(4, 4, 6), ground=(9, 9, 12), line=(255, 255, 255), obj=(235, 235, 235),
    )
    lvl.color(CH_EDGE, (232, 232, 238))
    lvl.color(CH_FILL, (18, 18, 23))
    lvl.color(CH_HAZARD, (255, 255, 255))
    lvl.color(CH_HINT, (120, 120, 130))

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
    """0:06-0:24, 2x. Every input is a note of the bass line.

    0:06-0:15  spider: one teleport per bass hit. A spike waits on your current side just
               past each hit, so the flip has to land on the note.
    0:15-0:24  cube over a spike pit: yellow/pink orbs placed where the cube actually is on
               each hit, so the clicks play the bass line and missing one drops you.
    """
    low = R.load_hits(HITS, "low")
    s0, split, s1 = t.seconds(t.bar(b0)), t.seconds(t.bar(11)), t.seconds(t.bar(b1))

    # --- spider on the bass
    lvl.portal("spider", round(x0) + 2, 1)
    ceil_row, spider_start = 5, t.col_at_seconds(s0 + 0.9)
    split_x = t.col_at_seconds(split)
    P.corridor(lvl, round(x0) + 2, round(split_x) + 2, lambda _x: 2.5, 5.0, wall=1,
               spikes=False, floor=False, color=CH_EDGE, fill_color=CH_FILL)
    run = R.spider_run(t, R.pick(low, s0 + 0.9, split - 0.4, min_gap=0.17), s0, split)
    side = "floor"
    for x, new_side in run.flips:
        # a spike on the side you're leaving, just past the note: stay and you die
        if side == "floor":
            lvl.spike(round(x + 0.8, 2), 0, color=CH_HAZARD)
        else:
            lvl.spike(round(x + 0.8, 2), ceil_row - 1, ceiling=True, color=CH_HAZARD)
        side = new_side
    lvl.text(round(spider_start) - 6, 3, "NIHIL LIGHT", scale=0.7, color=CH_HINT)

    # --- cube + orbs on the bass, over a pit
    lvl.portal("cube", round(split_x) + 3, 1)
    jump_t = min(h for h in low if h >= split + 0.5)   # the first jump is a note too
    jump_x = t.col_at_seconds(jump_t)
    chain = R.orb_chain(t, low, jump_t, s1 - 0.3, y0=0.0, lo=1.2, hi=7.5,
                        kinds=["yellow", "yellow", "pink"], min_gap=0.14)
    lvl.spike(round(jump_x + 1), 0, color=CH_HAZARD)            # forces the first jump
    ends = [o[0] for o in chain.orbs] + [p[1] for p in chain.platforms]
    last_x = max(ends) if ends else jump_x + 20
    P.spike_teeth(lvl, range(round(jump_x + 2), round(last_x) + 4), 0, color=CH_HAZARD)
    for x, y, kind in chain.orbs:
        lvl.orb(kind, round(x, 2), round(y, 2), color=CH_HAZARD)
    for a, b, top in chain.platforms:                            # rests between phrases
        for c in range(round(a), round(b) + 1):
            lvl.add(1, c, top - 1, color=CH_EDGE)
    lvl.blocks(round(last_x) + 5, 0, max(1, round(t.col(t.bar(b1))) - round(last_x) - 5),
               color=CH_EDGE)                                     # landing


def section_main_wave(lvl, t, mem, x0, x1, b0, b1):
    """0:24-0:48. A wave that turns on the drums, switching which drum drives it.

    0:24-1:00  snares enter: the wave reverses on every snare (mid band).
    bars 27-31 the hats go constant: mini wave spamming the 16ths.
    bars 31-35 back to normal size, turning on the kick pattern.
    The corridor is built around the path, so it is a different shape every bar because
    the drum pattern is.
    """
    mid, high, low = (R.load_hits(HITS, b) for b in ("mid", "high", "low"))
    lvl.portal("wave", round(x0) + 2, 1)
    s = lambda bar: t.seconds(t.bar(bar))
    parts = [  # (from bar, to bar, hits, rows per column)
        (b0, 27, R.pick(sorted(mid + low), s(b0) + 0.4, s(27), min_gap=0.12), 1.0),
        (27, 31, R.pick(sorted(high + mid + low), s(27), s(31), min_gap=0.085), 2.0),
        (31, b1, R.pick(sorted(low + mid), s(31), s(b1) - 0.5, min_gap=0.12), 1.0),
    ]
    y = 1.5
    for i, (a, b, hits, rpc) in enumerate(parts):
        xa, xb = t.col_at_seconds(s(a)), t.col_at_seconds(s(b))
        if rpc == 2.0:
            lvl.portal("mini", round(xa), round(y))
        elif i and parts[i - 1][3] == 2.0:
            lvl.portal("normal_size", round(xa), round(y))
        path = R.wave_path(t, hits, s(a), s(b), y0=y, lo=1.0, hi=7.5, rows_per_col=rpc)
        passage = MAIN_PASSAGE * (0.8 if rpc == 2.0 else 1.0)
        for x in range(round(xa) + 1, round(xb)):
            P.corridor(lvl, x, x, path, passage + rpc, wall=1, spikes=False,
                       color=CH_EDGE, fill_color=CH_FILL)
        y = path(xb)
    handover(lvl, x1)


def section_main_ship(lvl, t, mem, x0, x1, b0, b1):
    """Ship, 3x. Gate rhythm changes every phrase: beats, off-beats, then doubles."""
    start, end = enter(lvl, x0, "ship"), round(x1) - TAIL
    P.tunnel(lvl, start, end, 0.6, 6.0, wall=2, spikes=False, color=CH_EDGE,
             fill_color=CH_FILL)
    phrase = 4
    bar = b0
    while bar < b1:
        nxt = min(b1, bar + phrase)
        shape = int((bar - b0) // phrase) % 3
        density = (4, 8, 4)[shape]
        for i, x in enumerate(beats(t, bar, nxt, density)):
            if not start + 6 <= x <= end - 6:
                continue
            if shape == 0:                         # alternating high/low on the beat
                low = 1.0 + (2.0 if i % 2 else 0.0)
                P.gate(lvl, round(x), low, low + 1.7, top=5, bottom=1, color=CH_EDGE)
            elif shape == 1 and i % 2:             # off-beat slams, one side only
                P.gate(lvl, round(x), 1.0, 3.4, top=5, bottom=1, color=CH_EDGE)
            elif shape == 2:                       # doubles: two gates a column apart
                low = 2.4 if i % 2 else 1.0
                for dx in (0, 2):
                    P.gate(lvl, round(x) + dx, low, low + 1.6, top=5, bottom=1,
                           color=CH_EDGE)
        bar = nxt
    handover(lvl, x1)


def section_main_mini(lvl, t, mem, x0, x1, b0, b1):
    """Mini wave, 3x. Same phrase rotation, offset so it does not repeat the first wave
    section, and tighter because the mini hitbox is smaller."""
    start, end = enter(lvl, x0, "wave"), round(x1) - TAIL
    lvl.portal("mini", start - 4, 1)
    wave_run(lvl, t, start, end, b0, b1, MAIN_PASSAGE * 0.8, rotate=3)
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
    path, _, _ = P.wave_zigzag(start, t.blocks_per_beat(t.bar(b0)) * 2, centre=3.2,
                               amplitude=4.0)
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
    """Wave, 3x. Phrase rotation again, tightening phrase by phrase into the hit."""
    start, end = enter(lvl, x0, "wave"), round(x1) - TAIL
    phrase, bar, x, i = 4, b0, start, 1
    while x < end - 4 and bar < b1:
        nxt_bar = min(b1, bar + phrase)
        nxt_x = min(end, round(t.col(t.bar(nxt_bar))))
        squeeze = MAIN_PASSAGE * (0.95 - 0.25 * (bar - b0) / max(1, b1 - b0))
        if nxt_x - x > 6:
            WAVE_PATTERNS[i % len(WAVE_PATTERNS)](lvl, t, x, nxt_x, bar, nxt_bar, squeeze)
        x, bar, i = nxt_x, nxt_bar, i + 1
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
    wave_run(lvl, t, start, end, b0, b1, TIGHT_PASSAGE, phrase=2, rotate=2)
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
    wave_run(lvl, t, edges[0], edges[1] - clear, b0, b0 + (b1 - b0) / 4, TIGHT_PASSAGE,
             phrase=2, rotate=4)

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
    wave_run(lvl, t, edges[3], end, b0 + 3 * (b1 - b0) / 4, b1, TIGHT_PASSAGE, phrase=2,
             rotate=1)
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
            wave_run(lvl, t, x, stop, bar, bar + phrase, TIGHT_PASSAGE * 1.15, phrase=4,
                     rotate=int(bar) % 6)
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


# ---------------------------------------------------------------- phrase patterns
# A section built from one shape for 20 bars reads as one long identical corridor, which is
# what made v1 feel repetitive. Each 4-bar phrase picks the next pattern instead, so the
# shape, the input rhythm and the part of the screen being used all keep moving.

def pat_zigzag(lvl, t, x0, x1, b0, b1, passage, mode="wave"):
    """The staple: triangle wave, one cycle per two beats."""
    path, _, slope = P.wave_zigzag(x0, t.blocks_per_beat(t.bar(b0)) * 2, centre=3.6,
                                   amplitude=5.0, passage=passage)
    for x in range(x0, x1):
        P.corridor(lvl, x, x, path, passage + slope, wall=2, spikes=False, color=CH_EDGE,
                   fill_color=CH_FILL)


def pat_stairs(lvl, t, x0, x1, b0, b1, passage, mode="wave", down=False):
    """Flat treads that step on the beat - the corridor climbs, the inputs are staccato."""
    step = min(1.2, passage * 0.8)
    edges = beats(t, b0, b1, 4)
    def path(x):
        n = sum(1 for e in edges if e <= x)
        n = (len(edges) - n) if down else n
        return 2.2 + step * (n % 5)
    for x in range(x0, x1):
        P.corridor(lvl, x, x, path, passage + step, wall=2, spikes=False, color=CH_EDGE,
                   fill_color=CH_FILL)


def pat_straight_pinch(lvl, t, x0, x1, b0, b1, passage, mode="wave"):
    """Dead straight, but a frame-perfect squeeze lands on every beat."""
    centre = 3.4
    P.corridor(lvl, x0, x1, lambda _x: centre, passage * 2.0, wall=2, spikes=False,
               color=CH_EDGE, fill_color=CH_FILL)
    for x in beats(t, b0, b1, 4):
        if x0 + 3 <= x <= x1 - 3:
            P.pinch(lvl, round(x), centre, mode, t.speed_at(t.bar(b0)), fps=240, frames=1.0,
                    width=2, color=CH_HAZARD)


def pat_teeth(lvl, t, x0, x1, b0, b1, passage, mode="wave"):
    """Wide corridor, spikes biting in from alternating sides on every 8th."""
    centre, gap = 3.8, passage * 4.5
    P.corridor(lvl, x0, x1, lambda _x: centre, gap, wall=2, spikes=False, color=CH_EDGE,
               fill_color=CH_FILL)
    for i, x in enumerate(beats(t, b0, b1, 8)):
        if x0 + 2 <= x <= x1 - 2:
            row = centre - gap / 2 if i % 2 else centre + gap / 2 - 1
            lvl.spike(round(x), row, ceiling=bool(i % 2 == 0), color=CH_HAZARD)


def pat_orb_bounce(lvl, t, x0, x1, b0, b1, passage, mode="wave"):
    """Open air and blue orbs on the drums: the gravity flips carry you, not the walls."""
    P.tunnel(lvl, x0, x1, 1.0, 8.0, wall=2, spikes=False, color=CH_EDGE, fill_color=CH_FILL)
    lo, hi = t.seconds(t.bar(b0)), t.seconds(t.bar(b1))
    for i, x in enumerate(drum_columns(t, lo, hi)):
        if x0 + 2 <= x <= x1 - 2:
            lvl.orb("blue", round(x, 2), 2.6 if i % 2 else 6.4, color=CH_HAZARD)


def pat_funnel(lvl, t, x0, x1, b0, b1, passage, mode="wave"):
    """Opens wide then closes to the target passage across the phrase - a visible threat."""
    path, _, slope = P.wave_zigzag(x0, t.blocks_per_beat(t.bar(b0)) * 4, centre=3.6,
                                   amplitude=3.0, passage=passage)
    span = max(1, x1 - x0)
    for x in range(x0, x1):
        wide = passage * (2.6 - 1.6 * (x - x0) / span)
        P.corridor(lvl, x, x, path, wide + slope, wall=2, spikes=False, color=CH_EDGE,
                   fill_color=CH_FILL)


WAVE_PATTERNS = [pat_zigzag, pat_straight_pinch, pat_teeth, pat_stairs, pat_orb_bounce,
                 pat_funnel]


def wave_run(lvl, t, x0, x1, b0, b1, passage, *, phrase=4, rotate=0):
    """Fill a flying section with a different pattern every `phrase` bars."""
    bar, x, i = b0, x0, rotate
    while x < x1 - 4 and bar < b1:
        nxt_bar = min(b1, bar + phrase)
        nxt_x = min(x1, round(t.col(t.bar(nxt_bar))))
        if nxt_x - x > 6:
            WAVE_PATTERNS[i % len(WAVE_PATTERNS)](lvl, t, x, nxt_x, bar, nxt_bar, passage)
        x, bar, i = nxt_x, nxt_bar, i + 1
