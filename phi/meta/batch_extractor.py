# -*- coding: utf-8 -*-
"""phi.meta.batch_extractor — parallel local feature extraction.

Extracts audio features from every track in the phi library using only
local tools (mutagen + librosa).  No API keys required.

Output: ~/.phi/meta_store.jsonl — one JSON object per line, one per track.
Existing records are updated (not duplicated) on re-runs.

Usage
-----
    # CLI — extract all tracks in state.json
    python -m phi.meta.batch_extractor

    # With options
    python -m phi.meta.batch_extractor --workers 6 --force

    # From Python
    from phi.meta.batch_extractor import run_extraction
    run_extraction(paths, workers=4, force=False)

Fields per record
-----------------
path            str     Absolute path to audio file
title           str
artist          str
album           str
genre           str     File-level genre tag (may be empty)
year            str
duration        float   Seconds
bpm             float   Librosa beat tracking estimate (60s window)
key             str     Chroma-estimated key e.g. "A"
key_idx         int     0–11 (C=0 … B=11)
loudness_rms    float   Mean RMS energy over first 60s
spectral_cent   float   Mean spectral centroid (Hz) — proxy for brightness
mood_heuristic  str     calm/chill/focused/energetic (BPM + RMS heuristic)
energy_heuristic float  0–1 estimated from RMS and spectral centroid
extracted_at    str     ISO timestamp
error           str     Set if extraction failed, other fields may be absent
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent.parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

META_STORE = Path.home() / ".phi" / "meta_store.jsonl"
STATE_FILE  = Path.home() / ".phi" / "state.json"

KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# ---------------------------------------------------------------------------
# Per-track extraction (runs in worker process)
# ---------------------------------------------------------------------------

def _extract_one(path: str) -> dict:
    """
    Extract all local features from *path*.
    Must be top-level (picklable) for multiprocessing.
    """
    result: dict = {"path": path, "extracted_at": datetime.now(timezone.utc).isoformat()}

    # ── mutagen tags ──────────────────────────────────────────────────────────
    try:
        from mutagen import File as MFile
        f = MFile(path, easy=True)
        if f is not None:
            tags = f.tags or {}

            def _get(key: str) -> str:
                v = tags.get(key, [])
                return v[0].strip() if v else ""

            result["title"]    = _get("title")    or os.path.splitext(os.path.basename(path))[0]
            result["artist"]   = _get("artist")
            result["album"]    = _get("album")
            result["genre"]    = _get("genre")
            result["year"]     = _get("date") or _get("year")
            result["duration"] = round(f.info.length, 2) if hasattr(f, "info") else 0.0
        else:
            result["error"] = "mutagen returned None"
            return result
    except Exception as e:
        result["error"] = f"mutagen: {e}"
        return result

    # ── librosa audio features (first 60s for speed) ─────────────────────────
    try:
        import librosa
        import numpy as np

        y, sr = librosa.load(path, duration=60, mono=True)

        if len(y) == 0:
            raise ValueError("empty audio signal")

        # ── rhythm ────────────────────────────────────────────────────────────
        tempo_arr, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(np.atleast_1d(tempo_arr)[0])

        # Onset strength — proxy for percussiveness / rhythmic density
        onset_env    = librosa.onset.onset_strength(y=y, sr=sr)
        onset_mean   = float(np.mean(onset_env))
        onset_std    = float(np.std(onset_env))

        # ── pitch / tonal ─────────────────────────────────────────────────────
        chroma       = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_mean  = np.mean(chroma, axis=1)
        key_idx      = int(np.argmax(chroma_mean))
        key_str      = KEYS[key_idx]
        # Chroma variance: how spread energy is across pitch classes (tonal complexity)
        chroma_var   = float(np.mean(np.var(chroma, axis=1)))

        # Tonnetz — 6D tonal centroid features (harmonic + melodic content)
        tonnetz      = librosa.feature.tonnetz(y=y, sr=sr)
        tonnetz_mean = [round(float(v), 4) for v in np.mean(tonnetz, axis=1)]

        # ── timbre ────────────────────────────────────────────────────────────
        # RMS loudness
        rms_frames   = librosa.feature.rms(y=y)
        rms          = float(np.mean(rms_frames))
        # Dynamic range: difference between loud and quiet moments (95th vs 5th pct)
        rms_db       = librosa.amplitude_to_db(rms_frames + 1e-9)
        dynamic_range = float(np.percentile(rms_db, 95) - np.percentile(rms_db, 5))

        # Spectral centroid (brightness)
        centroid     = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))

        # Spectral rolloff — frequency below which 85% of spectral energy falls
        rolloff      = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)))

        # Spectral bandwidth — spread of spectrum around centroid
        bandwidth    = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))

        # Spectral contrast — valley-to-peak difference across 6 frequency bands
        contrast     = librosa.feature.spectral_contrast(y=y, sr=sr, n_bands=6)
        contrast_mean = [round(float(v), 4) for v in np.mean(contrast, axis=1)]

        # Harmonic-to-percussive energy ratio
        y_harm, y_perc = librosa.effects.hpss(y)
        harm_energy  = float(np.mean(y_harm ** 2))
        perc_energy  = float(np.mean(y_perc ** 2))
        total_energy = harm_energy + perc_energy + 1e-12
        harmonic_ratio = harm_energy / total_energy   # 1.0 = fully harmonic

        # Zero crossing rate
        zcr          = float(np.mean(librosa.feature.zero_crossing_rate(y)))

        # MFCCs (first 13 — compact timbral fingerprint)
        mfcc         = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_mean    = [round(float(v), 4) for v in np.mean(mfcc, axis=1)]

        result.update({
            # rhythm
            "bpm":              round(bpm, 2),
            "onset_mean":       round(onset_mean, 5),
            "onset_std":        round(onset_std, 5),
            # tonal
            "key":              key_str,
            "key_idx":          key_idx,
            "chroma_var":       round(chroma_var, 6),
            "tonnetz_mean":     tonnetz_mean,
            # timbre
            "loudness_rms":     round(rms, 5),
            "dynamic_range":    round(dynamic_range, 3),
            "spectral_cent":    round(centroid, 1),
            "spectral_rolloff": round(rolloff, 1),
            "spectral_bw":      round(bandwidth, 1),
            "spectral_contrast": contrast_mean,
            "harmonic_ratio":   round(harmonic_ratio, 4),
            "zcr":              round(zcr, 5),
            "mfcc_mean":        mfcc_mean,
        })

        # ── heuristic mood + energy ───────────────────────────────────────────
        energy_est = min(1.0, rms / 0.15)
        result["energy_heuristic"] = round(energy_est, 3)

        if bpm < 75 and energy_est < 0.3:
            mood = "calm"
        elif bpm < 100 and energy_est < 0.5:
            mood = "chill"
        elif bpm < 130:
            mood = "focused"
        else:
            mood = "energetic"
        result["mood_heuristic"] = mood

    except Exception as e:
        result["librosa_error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# Store management
# ---------------------------------------------------------------------------

def load_store(store_path: Path = META_STORE) -> dict[str, dict]:
    """Load existing meta_store.jsonl → {path: record}."""
    records: dict[str, dict] = {}
    if not store_path.exists():
        return records
    with store_path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    records[rec["path"]] = rec
                except Exception:
                    pass
    return records


def save_store(records: dict[str, dict], store_path: Path = META_STORE) -> None:
    """Write {path: record} back to JSONL."""
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with store_path.open("w") as fh:
        for rec in records.values():
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Main extraction runner
# ---------------------------------------------------------------------------

TRACK_TIMEOUT = 25  # seconds — subprocess is hard-killed if it hangs longer

_WORKER = Path(__file__).parent / "_extract_worker.py"
_PYTHON  = sys.executable


def _extract_subprocess(path: str) -> dict:
    """
    Run extraction for *path* in a fresh subprocess with a hard timeout.

    Result is written to a temp file (not stdout pipe) so that any
    ffmpeg/audioread grandchild processes that inherit pipe fds cannot
    cause subprocess.run to hang after the Python worker exits.
    """
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        subprocess.run(
            [_PYTHON, str(_WORKER), path, tmp_path],
            timeout=TRACK_TIMEOUT,
            # No stdout/stderr pipes — grandchildren can't block us
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        data = Path(tmp_path).read_text().strip()
        if data:
            return json.loads(data)
        return {"path": path, "error": "worker wrote no output",
                "extracted_at": datetime.now(timezone.utc).isoformat()}
    except subprocess.TimeoutExpired:
        return {"path": path, "error": f"timeout after {TRACK_TIMEOUT}s",
                "extracted_at": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        return {"path": path, "error": str(exc),
                "extracted_at": datetime.now(timezone.utc).isoformat()}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def run_extraction(
    paths: list[str],
    *,
    workers: int = 4,
    force: bool = False,
    store_path: Path = META_STORE,
    verbose: bool = True,
) -> dict[str, dict]:
    """
    Extract features for all *paths* using a ThreadPoolExecutor where each
    thread manages one subprocess with a hard TRACK_TIMEOUT.

    Thread-per-subprocess avoids macOS fork/spawn multiprocessing issues while
    still running N tracks concurrently.  workers=4 gives ~4× speedup with
    modest memory usage (one Python process per slot, each loading 60s audio).

    Returns the updated records dict.
    """
    records = load_store(store_path)

    todo = paths if force else [
        p for p in paths
        if p not in records or "error" in records[p] or "bpm" not in records.get(p, {})
    ]

    if not todo:
        if verbose:
            print(f"All {len(paths)} tracks already extracted. Use --force to re-run.",
                  flush=True)
        return records

    if verbose:
        print(f"Extracting {len(todo)}/{len(paths)} tracks  "
              f"workers={workers}  timeout={TRACK_TIMEOUT}s/track…",
              flush=True)

    done     = 0
    timeouts = 0
    errors   = 0
    t0       = time.time()
    lock     = __import__("threading").Lock()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_extract_subprocess, p): p for p in todo}

        for fut in as_completed(futures):
            path = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:
                result = {"path": path, "error": str(exc),
                          "extracted_at": datetime.now(timezone.utc).isoformat()}

            with lock:
                if "timeout" in result.get("error", ""):
                    timeouts += 1
                elif "error" in result:
                    errors += 1
                records[path] = result
                done += 1
                _done = done

            if verbose and (_done % 25 == 0 or _done == 1):
                elapsed = time.time() - t0
                rate    = _done / elapsed
                eta     = (len(todo) - _done) / rate if rate > 0 else 0
                print(f"  {_done}/{len(todo)}  "
                      f"{rate:.2f} t/s  "
                      f"ETA {int(eta // 60)}m{int(eta % 60):02d}s  "
                      f"timeouts:{timeouts} errors:{errors}",
                      flush=True)

            if _done % 50 == 0:
                with lock:
                    save_store(records, store_path)

    save_store(records, store_path)

    elapsed = time.time() - t0
    ok  = sum(1 for r in records.values() if "bpm" in r)
    err = sum(1 for r in records.values() if "error" in r)
    if verbose:
        print(f"\n✓ Done in {elapsed / 60:.1f} min")
        print(f"  {ok} tracks extracted  |  {err} errors")
        print(f"  Store: {store_path}")

    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m phi.meta.batch_extractor",
        description="Extract local audio features for all phi library tracks.",
    )
    parser.add_argument("--workers", "-j", type=int, default=4,
                        help="Concurrent subprocesses (default: 4; each loads ~300MB RAM)")
    parser.add_argument("--force", action="store_true",
                        help="Re-extract even if record already exists")
    parser.add_argument("--store", type=Path, default=META_STORE,
                        help=f"Output JSONL path (default: {META_STORE})")
    args = parser.parse_args(argv)

    if not STATE_FILE.exists():
        print(f"ERROR: {STATE_FILE} not found. Run phi at least once.", file=sys.stderr)
        sys.exit(1)

    state = json.loads(STATE_FILE.read_text())
    paths = [p for p in state.get("playlist", []) if os.path.isfile(p)]
    print(f"Library: {len(paths)} tracks")

    run_extraction(paths, workers=args.workers, force=args.force, store_path=args.store)


if __name__ == "__main__":
    main()
