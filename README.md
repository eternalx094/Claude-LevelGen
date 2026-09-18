# GD Level Maker

Lets Claude design Geometry Dash levels from plain-English instructions and put them straight
into your **Created** levels list.

## Using it

Open a Claude Code session in this folder (it picks up `CLAUDE.md` automatically) and just
ask, e.g.:

- "Make me a 45 second hard level: cube, ship, wave, with a red/black theme and Clutterfunk."
- "In Neon Circuit, make the wave part tighter."
- "I keep dying at 63% in Neon Circuit, the jump feels impossible."
- "Look at my level 'wave test' and add a ship section after it."

Close Geometry Dash before Claude installs anything. GD rewrites its save file when it exits,
which would wipe the new level. Every install backs up the save first.

## Commands (what Claude runs for you)

```
python gd.py status
python gd.py list
python gd.py preview levels/neon_circuit.py     # text map + previews/Neon_Circuit.png
python gd.py install levels/neon_circuit.py     # --replace to update an installed one
python gd.py show "Level Name" --png
python gd.py restore                             # undo: roll back to the latest backup
```

Needs Python 3.10+ and Pillow (`pip install pillow`) for the preview images.
