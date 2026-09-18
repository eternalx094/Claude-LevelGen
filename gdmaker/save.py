"""Read and write Geometry Dash's local ("Created") levels save, CCLocalLevels.dat.

File format (Windows): every byte XOR 11 -> url-safe base64 -> gzip -> RobTop's plist XML.
Each level's object data (key k4) is itself gzip + url-safe base64.

GD keeps the whole save in memory and rewrites the file when it exits, so writing while the
game is open is pointless (and gets overwritten). `LocalLevels.save` refuses to do it.
"""
from __future__ import annotations

import base64
import datetime as dt
import os
import re
import subprocess
import zlib
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

SAVE_DIR = Path(os.path.expandvars(r"%LOCALAPPDATA%\GeometryDash"))
LEVELS_FILE = SAVE_DIR / "CCLocalLevels.dat"
GAME_MANAGER_FILE = SAVE_DIR / "CCGameManager.dat"
BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
KEEP_BACKUPS = 15
MAX_NAME_LENGTH = 20

_XOR_11 = bytes(i ^ 11 for i in range(256))


class GDRunningError(RuntimeError):
    pass


# ---------------------------------------------------------------- encoding

def _b64decode(data: str | bytes) -> bytes:
    if isinstance(data, str):
        data = data.encode()
    data = data.strip().rstrip(b"\x00")
    return base64.urlsafe_b64decode(data + b"=" * (-len(data) % 4))


def decompress(data: str | bytes) -> bytes:
    """url-safe base64 + gzip/zlib -> raw bytes (used for saves and level strings)."""
    return zlib.decompress(_b64decode(data), 15 | 32)  # 15|32: accept gzip or zlib header


def compress(data: bytes) -> str:
    packer = zlib.compressobj(9, zlib.DEFLATED, 31)  # 31: gzip container, like GD writes
    return base64.urlsafe_b64encode(packer.compress(data) + packer.flush()).decode()


def decode_level_string(k4: str) -> str:
    """The k4 value of a level entry -> plain 'header;obj;obj;...' string."""
    if k4.startswith("H4sI"):
        return decompress(k4).decode("utf-8")
    return k4  # very old levels store it uncompressed


def encode_level_string(level_string: str) -> str:
    return compress(level_string.encode("utf-8"))


def decode_save_file(raw: bytes) -> str:
    return decompress(raw.translate(_XOR_11)).decode("utf-8")


def encode_save_file(xml: str) -> bytes:
    return compress(xml.encode("utf-8")).encode().translate(_XOR_11)


# ---------------------------------------------------------------- plist helpers

def pairs(d: ET.Element) -> list[tuple[str, ET.Element]]:
    """RobTop dicts alternate <k>key</k><value/> children."""
    it = iter(d)
    return [(k.text or "", v) for k, v in zip(it, it)]


def _serialize(el: ET.Element, out: list[str]) -> None:
    tag = el.tag
    if tag in ("d", "dict"):
        if len(el) == 0 and tag == "d":
            out.append("<d />")
            return
        out.append(f"<{tag}>")
        for child in el:
            _serialize(child, out)
        out.append(f"</{tag}>")
    elif tag == "t":
        out.append("<t />")
    else:
        out.append(f"<{tag}>{escape(el.text or '')}</{tag}>")


def to_xml(root: ET.Element) -> str:
    attrs = "".join(f' {k}="{v}"' for k, v in root.attrib.items())
    out = [f'<?xml version="1.0"?><{root.tag}{attrs}>']
    for child in root:
        _serialize(child, out)
    out.append(f"</{root.tag}>")
    return "".join(out)


def _el(tag: str, text: str | None = None) -> ET.Element:
    e = ET.Element(tag)
    e.text = text
    return e


def entry_get(entry: ET.Element, key: str) -> str | None:
    for k, v in pairs(entry):
        if k == key:
            return "true" if v.tag == "t" else v.text
    return None


def entry_set(entry: ET.Element, key: str, tag: str, text: str | None = None) -> None:
    """Set a key on a level entry, replacing it in place if present."""
    children = list(entry)
    for i in range(0, len(children), 2):
        if children[i].text == key:
            entry.remove(children[i + 1])
            entry.insert(i + 1, _el(tag, text))
            return
    entry.append(_el("k", key))
    entry.append(_el(tag, text))


def entry_del(entry: ET.Element, key: str) -> None:
    children = list(entry)
    for i in range(0, len(children), 2):
        if children[i].text == key:
            entry.remove(children[i])
            entry.remove(children[i + 1])
            return


# ---------------------------------------------------------------- environment

def gd_running() -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq GeometryDash.exe", "/NH"],
        capture_output=True, text=True,
    ).stdout
    return "GeometryDash.exe" in out


_player_name: str | None = None


def player_name() -> str:
    """Name shown as the creator on new levels (read once from CCGameManager.dat)."""
    global _player_name
    if _player_name is None:
        _player_name = "Player"
        try:
            raw = GAME_MANAGER_FILE.read_bytes()
            xml = decompress(raw.translate(_XOR_11)).decode("utf-8", "replace")
            m = re.search(r"<k>playerName</k><s>([^<]*)</s>", xml)
            if m:
                _player_name = m.group(1)
        except (OSError, ValueError, zlib.error):
            pass
    return _player_name


def backup(path: Path = LEVELS_FILE) -> Path:
    """Timestamped copy. Backups of the real save live in ./backups; backups of a test
    copy go next to that copy so the two can never be mixed up by `restore`."""
    folder = BACKUP_DIR if path.resolve() == LEVELS_FILE.resolve() else path.parent / "backups"
    folder.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    dest = folder / f"{path.stem}-{stamp}{path.suffix}"
    dest.write_bytes(path.read_bytes())
    old = sorted(folder.glob(f"{path.stem}-*{path.suffix}"))
    for stale in old[:-KEEP_BACKUPS]:
        stale.unlink()
    return dest


def list_backups() -> list[Path]:
    return sorted(BACKUP_DIR.glob("CCLocalLevels-*.dat"))


# ---------------------------------------------------------------- the save

class LocalLevels:
    """The 'Created' levels list. Entries are kept as raw XML elements so every key GD
    wrote (stats, editor camera, ...) survives untouched; we only add/replace/remove."""

    def __init__(self, path: str | Path = LEVELS_FILE):
        self.path = Path(path)
        self._mtime = self.path.stat().st_mtime_ns
        self.root = ET.fromstring(decode_save_file(self.path.read_bytes()))
        top = dict(pairs(self.root[0]))
        self._llm01 = top["LLM_01"]
        self.binary_version = int(top["LLM_02"].text) if "LLM_02" in top else 47
        self.entries: list[ET.Element] = [v for k, v in pairs(self._llm01) if k.startswith("k_")]

    # ---- queries
    def names(self) -> list[str]:
        return [entry_get(e, "k2") or "" for e in self.entries]

    def find(self, name: str) -> ET.Element | None:
        for e in self.entries:
            if entry_get(e, "k2") == name:
                return e
        lowered = [e for e in self.entries if (entry_get(e, "k2") or "").lower() == name.lower()]
        return lowered[0] if len(lowered) == 1 else None

    def level_string(self, name: str) -> str:
        entry = self.require(name)
        return decode_level_string(entry_get(entry, "k4") or "")

    def require(self, name: str) -> ET.Element:
        entry = self.find(name)
        if entry is None:
            raise KeyError(f"No level named {name!r}. Levels: {', '.join(self.names()[:15])}...")
        return entry

    # ---- edits
    def add(self, entry: ET.Element, replace: bool = False) -> str:
        """Put a new level at the top of the Created list. With replace=True an existing
        level of the same name is overwritten in place (keeping its list position)."""
        name = entry_get(entry, "k2") or ""
        existing = self.find(name)
        if existing is not None:
            if not replace:
                raise ValueError(f"A level named {name!r} already exists (use replace).")
            self.entries[self.entries.index(existing)] = entry
            return "replaced"
        self.entries.insert(0, entry)
        return "added"

    def set_level_string(self, name: str, level_string: str) -> None:
        """Swap only the object data of an existing level; stats and editor state are kept.
        Verification is cleared - the old verify run no longer applies to the new layout."""
        entry = self.require(name)
        entry_set(entry, "k4", "s", encode_level_string(level_string))
        entry_set(entry, "k48", "i", str(max(0, level_string.count(";") - 1)))
        entry_del(entry, "k14")  # verified
        entry_del(entry, "k34")  # verification replay

    def remove(self, name: str) -> None:
        self.entries.remove(self.require(name))

    # ---- output
    def to_xml(self) -> str:
        for child in list(self._llm01):
            self._llm01.remove(child)
        self._llm01.append(_el("k", "_isArr"))
        self._llm01.append(_el("t"))
        for i, entry in enumerate(self.entries):
            self._llm01.append(_el("k", f"k_{i}"))
            self._llm01.append(entry)
        return to_xml(self.root)

    def save(self, make_backup: bool = True) -> Path | None:
        is_real_save = self.path.resolve() == LEVELS_FILE.resolve()
        if is_real_save and gd_running():
            raise GDRunningError(
                "Geometry Dash is running. Close it first - it rewrites the save on exit "
                "and would wipe this change."
            )
        if self.path.stat().st_mtime_ns != self._mtime:
            raise RuntimeError("The save changed on disk since it was loaded. Reload and retry.")

        data = encode_save_file(self.to_xml())
        ET.fromstring(decode_save_file(data))  # never write something we can't read back

        backup_path = backup(self.path) if make_backup else None
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_bytes(data)
        if is_real_save and gd_running():
            tmp.unlink()
            raise GDRunningError("Geometry Dash was started while saving. Nothing was changed.")
        os.replace(tmp, self.path)
        self._mtime = self.path.stat().st_mtime_ns
        return backup_path


def restore(backup_file: str | Path, path: Path = LEVELS_FILE) -> None:
    if path.resolve() == LEVELS_FILE.resolve() and gd_running():
        raise GDRunningError("Close Geometry Dash before restoring a backup.")
    data = Path(backup_file).read_bytes()
    ET.fromstring(decode_save_file(data))
    backup(path)
    path.write_bytes(data)
