"""Geometry Dash level maker CLI.

    python gd.py status                      is GD running? where is the save? backups?
    python gd.py list                        levels in your Created list
    python gd.py show "Name" [--from X --to Y] [--png]
                                             text map (+ image) of a level in the save
    python gd.py ids "Name"                  which object IDs a level uses (learn new IDs)
    python gd.py preview levels/foo.py       build a level script -> previews/*.png + text map
    python gd.py install levels/foo.py [--replace]
                                             build it and put it in GD (GD must be closed)
    python gd.py remove "Name"               delete a level from the save (backed up first)
    python gd.py restore [backup-file]       roll the save back (latest backup by default)

Every command takes --save PATH to work on a copy of CCLocalLevels.dat instead.
A level script is a .py file with a `build()` function returning a gdmaker.Level.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from gdmaker import objects as O  # noqa: E402
from gdmaker.level import Level  # noqa: E402
from gdmaker.preview import render_ascii, render_png  # noqa: E402
from gdmaker.save import (LEVELS_FILE, GDRunningError, LocalLevels, entry_del,  # noqa: E402
                          entry_get, entry_set, gd_running, list_backups, restore)

PREVIEW_DIR = ROOT / "previews"


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "level"


def load_script(path: str) -> Level:
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "build"):
        sys.exit(f"{path} has no build() function")
    level = module.build()
    if not isinstance(level, Level):
        sys.exit(f"{path}: build() must return a gdmaker.Level")
    return level


def report(level: Level, x0=None, x1=None, png=True, ascii_map=True) -> None:
    if ascii_map:
        print(render_ascii(level, x0, x1))
    if png:
        out = render_png(level, PREVIEW_DIR / f"{_slug(level.name)}.png", x0, x1)
        print(f"\npreview image: {out}")
    warnings = level.lint()
    print(f"\n{len(level.objects)} objects, ends around col {level.length:.0f} "
          f"(~{level.length / O.SPEED_BLOCKS_PER_SECOND['1x']:.0f}s at 1x)")
    if warnings:
        print("lint warnings:")
        for w in warnings:
            print("  -", w)
    else:
        print("lint: no problems found")


def cmd_status(args) -> None:
    path = Path(args.save)
    print(f"save file:   {path} ({'found' if path.exists() else 'MISSING'})")
    print(f"GD running:  {'yes - close it before install/remove/restore' if gd_running() else 'no'}")
    if path.exists():
        save = LocalLevels(path)
        print(f"levels:      {len(save.entries)} in the Created list")
    backups = list_backups()
    print(f"backups:     {len(backups)}" + (f" (latest {backups[-1].name})" if backups else ""))


def cmd_list(args) -> None:
    save = LocalLevels(args.save)
    for i, entry in enumerate(save.entries):
        count = entry_get(entry, "k48") or "?"
        verified = " verified" if entry_get(entry, "k14") == "true" else ""
        print(f"{i:>3}  {entry_get(entry, 'k2')!s:<22} {count:>7} objects{verified}")


def cmd_show(args) -> None:
    save = LocalLevels(args.save)
    level = Level.from_entry(save.require(args.name))
    report(level, args.x0, args.x1, png=args.png)


def cmd_ids(args) -> None:
    save = LocalLevels(args.save)
    level = Level.from_entry(save.require(args.name))
    counts = Counter(o.id for o in level.objects)
    first = {}
    for o in level.objects:
        first.setdefault(o.id, o)
    for oid, n in counts.most_common():
        o = first[oid]
        extra = {k: v for k, v in o.items() if k not in ("1", "2", "3", "155")}
        print(f"{oid:>6}  x{n:<6} {O.describe(oid):<22} first at col {o.col:g} row {o.row:g}  "
              f"keys {extra}")


def cmd_preview(args) -> None:
    report(load_script(args.script), args.x0, args.x1)


def cmd_install(args) -> None:
    level = load_script(args.script)
    report(level, png=True, ascii_map=False)
    if any("impossible" in w for w in level.lint()) and not args.force:
        sys.exit("\nNot installed: fix the 'impossible' lint warnings first (or pass --force).")
    save = LocalLevels(args.save)
    existing = save.find(level.name)
    if existing is not None:
        if not args.replace:
            sys.exit(f"\nA level called {level.name!r} already exists. Use --replace to update "
                     f"its layout (stats are kept), or rename the level.")
        save.set_level_string(level.name, level.level_string())
        new = level.to_entry(binary_version=save.binary_version)
        # the description follows the script; the song does not - whatever you picked in
        # game (Jukebox, a NONG, an official track) is yours and survives a rebuild
        value = entry_get(new, "k3")
        if value is None:
            entry_del(existing, "k3")
        else:
            entry_set(existing, "k3", "s", value)
        if entry_get(existing, "k45") is None and entry_get(existing, "k8") is None:
            for key in ("k8", "k45"):
                if entry_get(new, key) is not None:
                    entry_set(existing, key, "i", entry_get(new, key))
        action = "updated"
    else:
        save.add(level.to_entry(binary_version=save.binary_version))
        action = "added to the top of your Created levels"
    try:
        backup = save.save()
    except GDRunningError as e:
        sys.exit(f"\nNot installed: {e}")
    print(f"\n{level.name!r} {action}. Backup of the previous save: {backup}")


def cmd_remove(args) -> None:
    save = LocalLevels(args.save)
    save.remove(args.name)
    try:
        backup = save.save()
    except GDRunningError as e:
        sys.exit(f"Not removed: {e}")
    print(f"Removed {args.name!r}. Backup: {backup}")


def cmd_restore(args) -> None:
    if not args.file and Path(args.save).resolve() != LEVELS_FILE.resolve():
        sys.exit("With --save, name the backup file to restore explicitly.")
    backups = list_backups()
    target = Path(args.file) if args.file else (backups[-1] if backups else None)
    if target is None:
        sys.exit("No backups yet.")
    try:
        restore(target, Path(args.save))
    except GDRunningError as e:
        sys.exit(str(e))
    print(f"Restored {target.name}. (The save you replaced was backed up too.)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--save", default=str(LEVELS_FILE), help="path to CCLocalLevels.dat")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("list").set_defaults(fn=cmd_list)

    s = sub.add_parser("show")
    s.add_argument("name")
    s.add_argument("--from", dest="x0", type=float)
    s.add_argument("--to", dest="x1", type=float)
    s.add_argument("--png", action="store_true")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("ids")
    s.add_argument("name")
    s.set_defaults(fn=cmd_ids)

    s = sub.add_parser("preview")
    s.add_argument("script")
    s.add_argument("--from", dest="x0", type=float)
    s.add_argument("--to", dest="x1", type=float)
    s.set_defaults(fn=cmd_preview)

    s = sub.add_parser("install")
    s.add_argument("script")
    s.add_argument("--replace", action="store_true")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_install)

    s = sub.add_parser("remove")
    s.add_argument("name")
    s.set_defaults(fn=cmd_remove)

    s = sub.add_parser("restore")
    s.add_argument("file", nargs="?")
    s.set_defaults(fn=cmd_restore)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
