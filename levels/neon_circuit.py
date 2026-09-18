"""Neon Circuit - demo level.

Brief: "a ~35 second level that tours the gamemodes: cube -> ship -> ball -> wave -> cube,
neon colours that shift every section, fair for a decent player, song Base After Base."

Design notes (1x speed, ~10.4 blocks/s; cube jump ~4 blocks long, ~2 high):
- cube A    0-95   warm-up: singles, a double, platform hop, pad onto a wall, orb over a
                   4-spike pit (orb sits at the jump's apex so the natural arc hits it), stairs.
                   Every obstacle leaves >= 2.5 blocks after the previous landing.
- ship     96-183  alternating ceiling/floor pillars 8 apart, two offset tunnels, then a
                   funnel down to rows 0-2 so the ship is guaranteed to hit the ball portal.
- ball    184-249  ceiling of blocks at row 5; floor and ceiling spikes alternate, spacing
                   tightening from 8 to 6 blocks (a flip takes ~2.6 blocks).
- wave    250-303  single-column gates with 3-row windows; window centres move <= 4 rows
                   per 5+ columns (the wave travels 1 row per column), then a low tunnel.
- cube B  301-375  finale: harder mix incl. one triple spike, orb pit, spiked staircase, GG.
"""
from gdmaker import Level

CH_BLOCK, CH_SPIKE = 1, 2


def build() -> Level:
    lvl = Level(
        "Neon Circuit",
        description="A quick tour of the gamemodes in neon. Designed and built by Claude.",
        song="Base After Base",
        bg=(18, 10, 40), ground=(30, 16, 70), line=(0, 255, 230),
    )
    lvl.color(CH_BLOCK, (0, 255, 220), blending=True)
    lvl.color(CH_SPIKE, (255, 60, 150), blending=True)

    def block(x, y=0, length=1):
        lvl.blocks(x, y, length, color=CH_BLOCK)

    def wall(x0, y0, x1, y1):
        lvl.fill(x0, y0, x1, y1, color=CH_BLOCK)

    def spike(x, y=0, count=1, ceiling=False):
        for i in range(count):
            lvl.spike(x + i, y, ceiling=ceiling, color=CH_SPIKE)

    def recolor(x, bg, blocks, duration=0.6):
        lvl.color_trigger(x, 1000, bg, duration)
        lvl.color_trigger(x, 1001, tuple(min(255, c + 14) for c in bg), duration)
        lvl.color_trigger(x, CH_BLOCK, blocks, duration)

    # ---------------------------------------------------------------- intro
    lvl.text(5, 4, "Neon Circuit", scale=0.8)
    lvl.text(5, 3, "built by Claude", scale=0.4)

    # ---------------------------------------------------------------- cube A (0-95)
    spike(12)
    spike(19)
    spike(25, count=2)
    block(32, 0, 10)                # platform 32-41 ...
    spike(38, 1)                    # ... with a spike on top (land ~34, jump ~37)
    spike(45, count=2)
    lvl.pad("yellow", 51)           # pad onto a 2-high wall
    wall(54, 0, 61, 1)
    spike(67, count=2)
    spike(74, count=4)              # 4-spike pit: jump at ~73, orb at the arc's apex
    lvl.orb("yellow", 75, 2)
    block(84, 0, 3)                 # stairs with a spike in the gap
    spike(87)
    wall(88, 0, 90, 1)

    # ---------------------------------------------------------------- ship (96-183)
    recolor(95, (35, 0, 55), (255, 90, 230))
    lvl.portal("ship", 96)

    def ceiling_pillar(x):          # pass underneath (rows 0-4)
        wall(x, 6, x, 11)
        spike(x, 5, ceiling=True)

    def floor_pillar(x):            # pass over (rows 5-9)
        wall(x, 0, x, 3)
        spike(x, 4)

    for i, x in enumerate(range(106, 147, 8)):
        (ceiling_pillar if i % 2 == 0 else floor_pillar)(x)

    wall(152, 0, 159, 2)            # tunnel: rows 3-6 open
    wall(152, 7, 159, 11)
    wall(162, 0, 168, 4)            # tunnel: rows 5-8 open
    wall(162, 9, 168, 11)
    wall(176, 3, 186, 11)           # funnel down to rows 0-2 for the portal

    # ---------------------------------------------------------------- ball (184-249)
    recolor(182, (0, 25, 55), (80, 200, 255))
    lvl.portal("ball", 184)
    block(187, 5, 60)               # ceiling 187-246 at row 5 (ball rides row 4 up there)
    spike(194, count=2)                      # floor spikes -> be on the ceiling
    spike(202, 4, count=2, ceiling=True)     # ceiling spikes -> be on the floor
    spike(210, count=2)
    spike(217, 4, count=2, ceiling=True)
    spike(224, count=2)
    spike(230, 4, count=2, ceiling=True)
    spike(236, count=3)
    spike(242, 4, count=3, ceiling=True)     # ends on the floor for the wave portal

    # ---------------------------------------------------------------- wave (250-303)
    recolor(248, (45, 0, 25), (255, 120, 60))
    lvl.portal("wave", 250)

    def gate(x, low, high):         # column of blocks with an open window rows low..high
        if low > 0:
            wall(x, 0, x, low - 1)
        wall(x, high + 1, x, 11)

    for x, low in ((258, 3), (264, 6), (270, 2), (275, 5), (280, 1), (285, 4), (290, 0)):
        gate(x, low, low + 2)
    wall(294, 3, 303, 11)           # low tunnel (rows 0-2) through the cube portal

    # ---------------------------------------------------------------- cube B (301-375)
    recolor(299, (18, 10, 40), (0, 255, 220))
    lvl.portal("cube", 301)
    spike(309)
    spike(315, count=2)
    block(321, 0, 10)
    spike(327, 1)
    spike(335, count=4)
    lvl.orb("yellow", 336, 2)
    spike(345, count=3)             # the one triple spike
    block(352, 0, 3)
    spike(355)
    wall(356, 0, 358, 1)
    spike(359)
    wall(360, 0, 362, 2)

    lvl.color_trigger(364, 1000, (90, 40, 140), 1.5)
    lvl.text(372, 3, "GG", scale=1.0)
    return lvl
