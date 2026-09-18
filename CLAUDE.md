# GD Level Maker — how to build Geometry Dash levels from the user's instructions

You are the level designer. The user describes what they want ("an easy neon ship level",
"make the drop at 40% harder", "I keep dying at 63%") and you design it by hand in a Python
level script, check it, and install it into their game. Don't reach for random/procedural
generation. Every obstacle should be a deliberate choice you could explain.

## Workflow

1. **Understand the brief.** Length, difficulty, gamemodes, theme/colours, song. Fill gaps
   with sensible defaults and say what you assumed instead of interrogating the user.
2. **Plan sections on paper first**: a table of column ranges → gamemode, speed, idea.
   Time ↔ distance: `seconds × blocks/s` (0.5x 8.37, 1x 10.39, 2x 12.91, 3x 15.6, 4x 19.2).
   A 60 s level at 1x is ~620 columns.
3. **Write `levels/<slug>.py`** with a `build()` returning a `gdmaker.Level`. Put the brief
   and your design notes in the docstring (see `levels/neon_circuit.py`). Use small local
   helpers (pillar(), gate(), recolor()) so the layout reads like a design, not a dump.
4. **Check it**: `python gd.py preview levels/<slug>.py` prints a text map + lint warnings and
   writes `previews/<Name>.png`. **Look at the PNG** (Read it) and walk the player's path
   section by section against the physics notes below. Fix, re-preview, repeat.
5. **Install**: `python gd.py install levels/<slug>.py` (add `--replace` to update a level
   already installed). GD must be closed. The tool refuses otherwise, because GD rewrites
   its save on exit and would wipe the change. Every write backs the save up first.
6. **Iterate on feedback.** "Died at 43%" → `level.col_at_percent(43)` (approximate) →
   inspect that area with `--from/--to` and fix it. Before `--replace`, check whether the
   user edited the level in GD (`python gd.py show "<Name>"`). If they did, load their
   version with `Level.from_entry(...)` and edit that rather than overwriting their work.

Other commands: `status`, `list`, `show "<Name>" [--from X --to Y] [--png]`,
`ids "<Name>"` (object IDs + their keys in a level, so you can learn any object the user
places), `remove "<Name>"`, `restore [file]`. Add `--save <copy.dat>` before the command to
work on a copy (useful for experiments while GD is open).

## Coordinates and the API (`gdmaker/level.py`)

- x = column, 0 = player start, grows right. y = row above the ground, 0 = sitting on the
  ground. Floats allowed. The API converts to GD units (30 per block, object centres) and
  applies the editor's snap offsets (pads and small spikes sit on the cell floor).
- `lvl.block/blocks/column/fill/slab`, `lvl.spike(x, y, size=, ceiling=)`, `lvl.spikes`,
  `lvl.orb(kind, x, y)`, `lvl.pad(kind, x, y, ceiling=)`, `lvl.portal(kind, x, y=1)`,
  `lvl.speed("2x", x)`, `lvl.coin`, `lvl.text`, `lvl.start_pos(x, y, gamemode=, speed=)`.
- Any object: `lvl.add(obj_id, x, y, rotation=, flip_x=, flip_y=, scale=, color=,
  detail_color=, groups=[...], z_layer=, z_order=, raw={key: value})`.
- Colours: `Level(bg=, ground=, ground2=, line=, obj=)`, `lvl.color(channel, rgb,
  blending=)` for custom channels 1–999, then `color=channel` on objects.
- Triggers (fire when the player's x passes them; placed at row -3 by default):
  `color_trigger(x, channel, rgb, duration)`, `move(x, group, dx, dy, duration, easing)`
  (dx/dy in blocks), `alpha(x, group, opacity, duration)`, `toggle(x, group, on)`,
  `spawn(x, group, delay)`, generic `trigger(obj_id, x, raw={...})`. `lvl.new_group()`.
- Editing: `between(x0, x1)`, `where(pred)`, `remove(pred)`, `clear(x0, x1)`,
  `shift(from_x, by)` (lengthen/shorten a section without redoing the rest).
- Level settings: `Level(name, description=, song=<index or official name>, custom_song=<id>,
  gamemode=, speed=, mini=, dual=, flipped=, bg_texture=, ground_texture=, font=)`.
  Names ≤ 20 chars, descriptions ≤ 140.
- IDs live in `gdmaker/objects.py`. For anything missing, have the user place the object in
  a scratch level and run `python gd.py ids "<level>"`. Don't guess IDs.

## Physics cheat sheet (approximate — design with margin)

- **Cube** (1x): jump ≈ 4 blocks long, ≈ 2.1 blocks high; lands ~0.5 block sooner onto a
  1-high platform. Max 3 full spikes in a row at 1x (triple = hard). Step-ups of 1 block are
  easy, 2 blocks is the limit. Leave ≥ 2.5 blocks between a landing and the next takeoff.
  Jump length scales with speed (≈ 5 at 2x, 6 at 3x); height doesn't.
- **Yellow orb/pad**: roughly a normal jump / ~1.4× jump. Put an orb near the *apex* of the
  natural jump (row 2 when jumping from the ground, ~2 columns after takeoff) so the arc
  passes through it. An orb there lets the cube clear a 4-spike pit.
- **Blue orb/pad** flip gravity, **pink** is a small hop, **red** a big one, **green** flips
  gravity and jumps, **black** slams downward.
- **Ship / wave / UFO / swing** get a ~10-row corridor (rows 0–9) when the portal sits near
  the ground; **ball / spider** ≈ 8 rows. The ship slides safely along block tops/bottoms but
  dies on side faces. Keep ship gaps ≥ 3 rows for normal difficulty, pillars ≥ 6–8 apart.
- **Wave** moves 1 row per column (45°), mini wave ~2 rows per column. It dies on any block
  contact except the corridor's floor/ceiling. Window centres of consecutive gates should
  differ by ≤ (columns apart − 1) rows. 3-row windows are comfortable, 2 is hard.
- **Ball** flips gravity on click; a floor↔ceiling switch across 4 rows takes ~2.6 blocks.
- **Portals** are ~3 rows tall centred on `y`; y=1 catches a player running on the ground.
  When the previous mode can be anywhere vertically (ship, wave), build a funnel so the
  player has to pass through the next portal. Give ≥ 3 blocks after any portal before a hazard.
- Start with ≥ 10 empty columns. End with ~15 empty columns after the last obstacle.

## Design principles

- Read the brief's difficulty honestly: easy = singles and wide gaps; normal = doubles, orbs,
  simple ship; hard = triples, speed changes, gravity; insane/demon = tight corridors, dual,
  frequent mode swaps, fast speeds. Don't spike difficulty mid-level unless asked.
- Sections should feel different: vary rhythm, open space, and colour (a `recolor` at each
  portal is cheap and effective). Build to a climax, then give a short breather at the end.
- Readability beats cleverness: no blind jumps, no hazards hidden behind deco, no fake orbs.
- Sync to music when the user gives timestamps: `seconds_to_blocks(t, speed)` gives the column.
- Things you can't verify without playing are guesses. Say so, and ask the user to playtest
  and report percentages. Use `lvl.start_pos(...)` checkpoints to make testing sections easy
  (remove them before the user verifies/uploads).

## Safety rules

- Never write the real save while GD is running (the tool enforces this). Never delete a
  user's level unless they explicitly asked, and mention the backup when you do.
- Backups: `backups/` (last 15). `python gd.py restore` rolls back to the latest.
- Changing a level's layout clears its "verified" flag on purpose, because the old
  verification doesn't cover the new layout. Levels are for the user to verify legitimately.
