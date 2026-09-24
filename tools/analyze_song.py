"""Measure a song so a level can be synced to it: BPM, beat phase, and section changes.

    python tools/analyze_song.py "path/to/song.mp3" [--bpm 174]

Decodes with ffmpeg, then does everything else in numpy: spectral-flux onset envelope,
autocorrelation for tempo, phase search for the downbeat, RMS for loud/quiet sections.
Prints the numbers to paste into a level script's Timeline.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

import numpy as np

SR = 22050
N_FFT = 1024
HOP = 256
FPS = SR / HOP  # onset frames per second


def decode(path: str) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True)
    if not out.stdout:
        sys.exit(f"ffmpeg could not decode {path}\n{out.stderr.decode()[:500]}")
    return np.frombuffer(out.stdout, np.int16).astype(np.float32) / 32768.0


def spectrogram(x: np.ndarray) -> np.ndarray:
    n = 1 + (len(x) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    return np.abs(np.fft.rfft(x[idx] * np.hanning(N_FFT), axis=1))


def onset_envelope(S: np.ndarray) -> np.ndarray:
    flux = np.maximum(0.0, np.diff(np.log1p(S * 100), axis=0)).sum(axis=1)
    flux = np.concatenate([[0.0], flux])
    local = np.convolve(flux, np.ones(int(FPS)) / FPS, mode="same")
    return np.maximum(0.0, flux - local)


def estimate_bpm(env: np.ndarray, lo: float = 60, hi: float = 200) -> list[tuple[float, float]]:
    e = env - env.mean()
    ac = np.correlate(e, e, mode="full")[len(e) - 1:]
    lags = np.arange(len(ac))
    bpms = np.where(lags > 0, 60.0 * FPS / np.maximum(lags, 1), 0)
    ok = (bpms >= lo) & (bpms <= hi)
    scores = np.where(ok, ac / (np.max(np.abs(ac)) or 1), -1)
    peaks = [i for i in range(2, len(scores) - 2)
             if scores[i] > scores[i - 1] and scores[i] >= scores[i + 1] and scores[i] > 0.1]
    peaks.sort(key=lambda i: -scores[i])
    return [(float(bpms[i]), float(scores[i])) for i in peaks[:6]]


def best_phase(env: np.ndarray, bpm: float) -> tuple[float, float]:
    """Offset in seconds of the first beat, and how strongly the grid lands on onsets."""
    period = 60.0 / bpm * FPS
    best, best_score = 0.0, -1.0
    for phase in np.arange(0, period, 0.25):
        beats = np.arange(phase, len(env) - 1, period)
        idx = np.clip(np.round(beats).astype(int), 0, len(env) - 1)
        score = float(env[idx].mean())
        if score > best_score:
            best, best_score = float(phase) / FPS, score
    return best, best_score / (env.mean() or 1)


def sections(x: np.ndarray, win: float = 1.0) -> list[tuple[float, float, float]]:
    n = int(SR * win)
    frames = len(x) // n
    rms = np.sqrt((x[:frames * n].reshape(frames, n) ** 2).mean(axis=1))
    loud = 20 * np.log10(np.maximum(rms, 1e-6))
    out, start, level = [], 0, loud[0]
    for i in range(1, frames):
        if abs(loud[i] - level) > 6 and i - start >= 3:   # 6 dB step = a real section change
            out.append((start * win, i * win, float(loud[start:i].mean())))
            start, level = i, loud[i]
        else:
            level = 0.7 * level + 0.3 * loud[i]
    out.append((start * win, frames * win, float(loud[start:frames].mean())))
    return out


def band_onsets(x: np.ndarray, lo_hz: float, hi_hz: float, min_gap: float = 0.09,
                strength: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Onset times in a frequency band (drums live low), with their strengths."""
    S = spectrogram(x)
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    band = S[:, (freqs >= lo_hz) & (freqs <= hi_hz)]
    flux = np.maximum(0.0, np.diff(np.log1p(band * 100), axis=0)).sum(axis=1)
    flux = np.concatenate([[0.0], flux])
    smooth = np.convolve(flux, np.ones(int(FPS * 0.5)) / (FPS * 0.5), mode="same")
    detect = flux - smooth
    thresh = detect.mean() + strength * detect.std()
    gap = int(min_gap * FPS)
    times, values, last = [], [], -gap
    for i in range(1, len(detect) - 1):
        if (detect[i] > thresh and detect[i] >= detect[i - 1] and detect[i] > detect[i + 1]
                and i - last >= gap):
            times.append(i / FPS)
            values.append(float(detect[i]))
            last = i
    return np.array(times), np.array(values)


def _parse_time(text: str) -> float:
    mins, _, secs = text.partition(":")
    return float(mins) * 60 + float(secs) if secs else float(mins)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--bpm", type=float, help="force a BPM instead of estimating")
    ap.add_argument("--marks", nargs="*", default=[], help="times like 2:33 to locate on the grid")
    ap.add_argument("--onsets", nargs=2, metavar=("START", "END"),
                    help="list drum onsets between two times, e.g. --onsets 2:06 4:04")
    ap.add_argument("--band", nargs=2, type=float, default=(30, 200), metavar=("LO", "HI"),
                    help="frequency band for onset detection (default 30-200 Hz: kicks)")
    ap.add_argument("--min-gap", type=float, default=0.09, help="minimum seconds between onsets")
    ap.add_argument("--out", help="write the onset times to a JSON file")
    args = ap.parse_args()

    if args.onsets:
        import json
        x = decode(args.path)
        t0, t1 = _parse_time(args.onsets[0]), _parse_time(args.onsets[1])
        times, values = band_onsets(x, *args.band, min_gap=args.min_gap)
        keep = times[(times >= t0) & (times <= t1)]
        bpm = args.bpm or 175.186
        print(f"{len(keep)} onsets between {args.onsets[0]} and {args.onsets[1]} "
              f"({len(keep) / (t1 - t0):.1f}/s, band {args.band[0]:.0f}-{args.band[1]:.0f} Hz)")
        gaps = np.diff(keep)
        if len(gaps):
            sixteenth = 60.0 / bpm / 4
            print(f"gaps: min {gaps.min():.3f}s  median {np.median(gaps):.3f}s  max {gaps.max():.3f}s"
                  f"  (1/16 note = {sixteenth:.3f}s)")
            print("gap histogram in 16th notes:",
                  {f"{k}/16": int(v) for k, v in
                   zip(*np.unique(np.round(gaps / sixteenth).astype(int), return_counts=True))})
        for t in keep[:12]:
            print(f"  {int(t // 60)}:{t % 60:06.3f}")
        if args.out:
            with open(args.out, "w") as fh:
                json.dump({"song": args.path, "band": list(args.band),
                           "times": [round(float(t), 4) for t in keep]}, fh, indent=1)
            print("wrote", args.out)
        return

    x = decode(args.path)
    dur = len(x) / SR
    S = spectrogram(x)
    env = onset_envelope(S)

    print(f"file      {args.path}")
    print(f"duration  {dur:.2f}s  ({int(dur // 60)}:{dur % 60:05.2f})")

    candidates = estimate_bpm(env)
    print("tempo candidates (bpm, strength):",
          ", ".join(f"{b:.2f} ({s:.2f})" for b, s in candidates))
    bpm = args.bpm or (candidates[0][0] if candidates else 120.0)
    offset, tightness = best_phase(env, bpm)
    print(f"chosen    bpm {bpm:.3f}, first beat at {offset:.3f}s, grid lands {tightness:.2f}x "
          f"above average onset strength")
    beat_s = 60.0 / bpm
    print(f"          1 beat {beat_s:.4f}s | 1 bar (4/4) {4 * beat_s:.4f}s | "
          f"{dur / (4 * beat_s):.1f} bars total")

    print("\nsections (1s resolution, 6 dB change):")
    print("   start      end    len   level")
    for s, e, lv in sections(x):
        print(f"  {int(s // 60)}:{s % 60:05.2f}  {int(e // 60)}:{e % 60:05.2f}  "
              f"{e - s:>5.1f}s  {lv:>6.1f} dB")

    if args.marks:
        print("\nrequested marks:")
        for m in args.marks:
            mins, _, secs = m.partition(":")
            t = float(mins) * 60 + float(secs) if secs else float(mins)
            beat = (t - offset) / beat_s
            print(f"  {m:>6}  =  {t:7.2f}s  =  beat {beat:8.2f}  =  bar {beat / 4:7.2f} "
                  f"(nearest bar line {round(beat / 4)} at "
                  f"{offset + round(beat / 4) * 4 * beat_s:.2f}s)")


if __name__ == "__main__":
    main()
