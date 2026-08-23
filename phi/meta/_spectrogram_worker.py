# -*- coding: utf-8 -*-
"""phi.meta._spectrogram_worker — subprocess spectrogram extractor.

Called by track_store.py as:
    python _spectrogram_worker.py <audio_path> <output_dir>

Writes three .npy files into <output_dir>/:
    mel_128.npy     float32 (T, 128)  log-mel spectrogram
    chroma_12.npy   float32 (T, 12)   chromagram (CQT-based)
    tonnetz_6.npy   float32 (T, 6)    tonal centroid features

Exits with code 0 on success, non-zero on failure.
Stderr is suppressed by the caller.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: _spectrogram_worker.py <audio_path> <output_dir>", file=sys.stderr)
        return 2

    audio_path = sys.argv[1]
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        import librosa
        import numpy as np
    except ImportError as exc:
        print(f"missing dependency: {exc}", file=sys.stderr)
        return 1

    try:
        # Load first 120s — enough for representative features
        y, sr = librosa.load(audio_path, duration=120, mono=True, sr=22050)
    except Exception as exc:
        print(f"load error: {exc}", file=sys.stderr)
        return 1

    if len(y) < 512:
        print("audio too short", file=sys.stderr)
        return 1

    hop  = 512
    n_fft = 2048

    try:
        # ── log-mel spectrogram (128 bins) ────────────────────────────────────
        mel = librosa.feature.melspectrogram(
            y=y, sr=sr, n_fft=n_fft, hop_length=hop, n_mels=128, fmax=sr // 2
        )
        mel_db = librosa.power_to_db(mel, ref=np.max).T  # (T, 128)
        np.save(str(output_dir / "mel_128.npy"), mel_db.astype(np.float32))
    except Exception as exc:
        print(f"mel error: {exc}", file=sys.stderr)
        return 1

    try:
        # ── chromagram (12 chroma bins, CQT-based) ────────────────────────────
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop).T  # (T, 12)
        np.save(str(output_dir / "chroma_12.npy"), chroma.astype(np.float32))
    except Exception as exc:
        print(f"chroma error: {exc}", file=sys.stderr)
        # Non-fatal — still return 0 if mel succeeded

    try:
        # ── tonal centroid (tonnetz, 6D) ─────────────────────────────────────
        tonnetz = librosa.feature.tonnetz(y=y, sr=sr, hop_length=hop).T  # (T, 6)
        np.save(str(output_dir / "tonnetz_6.npy"), tonnetz.astype(np.float32))
    except Exception as exc:
        print(f"tonnetz error: {exc}", file=sys.stderr)
        # Non-fatal

    return 0


if __name__ == "__main__":
    sys.exit(main())
