"""phi.metadata.extractor — librosa audio analysis → AudioFeatures.

Single public entry point:

    features = extract(path)           # Path → AudioFeatures
    features = extract_or_zero(path)   # never raises; zeroed on failure

librosa is loaded lazily so the module can be imported even if librosa has
not been installed yet — ImportError is raised only at call time.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from phi.metadata.schema import AudioFeatures

_SR: int = 22050          # sample rate used for all analysis
_HOP: int = 512           # hop length for frame-based features
_N_MFCC: int = 13         # MFCC coefficients


def extract(path: Path, sr: int = _SR) -> AudioFeatures:
    """Load audio from *path* and compute AudioFeatures.

    Parameters
    ----------
    path : local audio file (MP3, FLAC, WAV, OGG — any format librosa can read)
    sr   : target sample rate; default 22050 Hz

    Returns
    -------
    AudioFeatures
        All fields populated from librosa analysis.

    Raises
    ------
    ImportError   if librosa is not installed
    FileNotFoundError  if path does not exist
    RuntimeError  on librosa load failure
    """
    try:
        import librosa  # type: ignore[import]
        import librosa.feature  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "librosa is required for audio extraction. "
            "Install with: mamba install -c conda-forge librosa>=0.10"
        ) from exc

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    try:
        y, sr = librosa.load(str(path), sr=sr, mono=True)
    except Exception as exc:
        raise RuntimeError(f"librosa could not load {path}: {exc}") from exc

    # Tempo
    tempo_arr, _ = librosa.beat.beat_track(y=y, sr=sr, hop_length=_HOP)
    tempo = float(np.asarray(tempo_arr).ravel()[0]) if hasattr(tempo_arr, "__len__") else float(tempo_arr)

    # Loudness
    rms = librosa.feature.rms(y=y, hop_length=_HOP)
    loudness_db = float(librosa.amplitude_to_db(rms).mean())

    # ZCR
    zcr = float(librosa.feature.zero_crossing_rate(y, hop_length=_HOP).mean())

    # Spectral centroid + rolloff
    centroid = float(librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=_HOP).mean())
    rolloff = float(librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=_HOP).mean())

    # Chroma — 12-d mean over time
    chroma = librosa.feature.chroma_stft(y=y, sr=sr, hop_length=_HOP)
    chroma_mean: list[float] = chroma.mean(axis=1).tolist()

    # MFCC — 13-d mean over time
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=_N_MFCC, hop_length=_HOP)
    mfcc_mean: list[float] = mfcc.mean(axis=1).tolist()

    return AudioFeatures(
        tempo=tempo,
        loudness_db=loudness_db,
        zero_crossing_rate=zcr,
        spectral_centroid=centroid,
        spectral_rolloff=rolloff,
        chroma_mean=chroma_mean,
        mfcc_mean=mfcc_mean,
    )


def extract_or_zero(path: Path, sr: int = _SR) -> AudioFeatures:
    """extract() with a zero-filled fallback on any error.

    Safe to call in batch pipelines where individual files may be missing
    or corrupt.  Logs the failure path to stderr.
    """
    import sys
    try:
        return extract(path, sr=sr)
    except Exception as exc:
        print(f"[extractor] WARNING: {path.name} — {exc}", file=sys.stderr)
        return AudioFeatures()
