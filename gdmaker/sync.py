"""Beat <-> column maths, so a layout can be pinned to the music.

Distance per second depends on the current speed, so a column is only meaningful together
with the speed schedule. Build a Timeline, declare speed changes at beats, then ask it for
the column of any beat. Change the BPM later and the whole level rescales.

    t = Timeline(bpm=174, offset=0.31, speed="2x")
    t.set_speed(t.bar(16), "3x")
    lvl.spike(t.col(t.bar(4)))        # exactly on the downbeat of bar 5
    t.place_portals(lvl)              # writes the speed portals themselves
"""
from __future__ import annotations

from .objects import SPEED_BLOCKS_PER_SECOND


class Timeline:
    def __init__(self, bpm: float, offset: float = 0.0, speed: str = "1x",
                 beats_per_bar: int = 4, start_col: float = 0.0):
        self.bpm = bpm
        self.offset = offset          # seconds of audio before beat 0
        self.beats_per_bar = beats_per_bar
        self.start_col = start_col    # column the player is at when the song starts
        self._changes: list[tuple[float, str]] = [(0.0, speed)]  # (seconds, speed)

    # ---- time
    def bar(self, bar: float, beat: float = 0.0) -> float:
        """Beat number of `bar` (0-based) plus an offset in beats."""
        return bar * self.beats_per_bar + beat

    def seconds(self, beat: float) -> float:
        return self.offset + beat * 60.0 / self.bpm

    def beat_at_seconds(self, t: float) -> float:
        return (t - self.offset) * self.bpm / 60.0

    # ---- speed schedule
    def set_speed(self, beat: float, speed: str) -> None:
        if speed not in SPEED_BLOCKS_PER_SECOND:
            raise ValueError(f"unknown speed {speed!r}")
        t = self.seconds(beat)
        self._changes = sorted([c for c in self._changes if c[0] != t] + [(t, speed)])

    def speed_at(self, beat: float) -> str:
        t = self.seconds(beat)
        return [s for at, s in self._changes if at <= t][-1]

    # ---- distance
    def col_at_seconds(self, t: float) -> float:
        col = self.start_col
        for i, (at, speed) in enumerate(self._changes):
            if at >= t:
                break
            end = min(t, self._changes[i + 1][0] if i + 1 < len(self._changes) else t)
            col += SPEED_BLOCKS_PER_SECOND[speed] * (end - at)
        return col

    def col(self, beat: float) -> float:
        return self.col_at_seconds(self.seconds(beat))

    def beat_at_col(self, col: float) -> float:
        """Inverse of col(): which beat lands at this column."""
        t = 0.0
        travelled = self.start_col
        for i, (at, speed) in enumerate(self._changes):
            nxt = self._changes[i + 1][0] if i + 1 < len(self._changes) else None
            bps = SPEED_BLOCKS_PER_SECOND[speed]
            span = (nxt - at) if nxt is not None else float("inf")
            if travelled + bps * span >= col:
                t = at + (col - travelled) / bps
                return self.beat_at_seconds(t)
            travelled += bps * span
            t = nxt
        return self.beat_at_seconds(t)

    def beats_per_block(self, beat: float) -> float:
        """Handy for spacing patterns: beats it takes to cross one block right now."""
        return self.bpm / 60.0 / SPEED_BLOCKS_PER_SECOND[self.speed_at(beat)]

    def blocks_per_beat(self, beat: float) -> float:
        return SPEED_BLOCKS_PER_SECOND[self.speed_at(beat)] * 60.0 / self.bpm

    # ---- output
    def place_portals(self, level, y: float = 1) -> None:
        """Put the actual speed portals in the level at their scheduled columns."""
        for i, (at, speed) in enumerate(self._changes):
            if i == 0:
                continue  # the starting speed is a level setting, not a portal
            level.speed(speed, round(self.col_at_seconds(at), 3), y)

    def plan(self, marks: dict[str, float]) -> str:
        """Readable table of named beats -> time and column, for design notes."""
        rows = ["  beat      time     col   speed  name",
                "  ----  --------  ------  ------  ----"]
        for name, beat in sorted(marks.items(), key=lambda kv: kv[1]):
            rows.append(f"  {beat:>4.0f}  {self.seconds(beat):>7.2f}s  {self.col(beat):>6.0f}  "
                        f"{self.speed_at(beat):>6}  {name}")
        return "\n".join(rows)
