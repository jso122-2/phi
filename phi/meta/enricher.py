# -*- coding: utf-8 -*-
"""phi.meta.enricher — per-track enrichment pipeline.

Coordinates fingerprinting → AcoustID lookup → MusicBrainz fetch →
tag merge → optional write-back.

EnrichResult carries everything the caller needs:
  - merged_meta   : dict ready for Library.store_meta()
  - annotation    : dict ready for Library.store_annotation()
  - review_item   : set when confidence was below threshold (user must confirm)
  - wrote_tags    : True if file tags were actually updated on disk
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from phi.meta.acoustid_client import AcoustIDResult, best_match, fingerprint, lookup_raw
from phi.meta.mb_client       import MBRecording, MusicBrainzClient
from phi.meta.review_queue    import ReviewItem, ReviewQueue, ReviewStatus


# ── result ────────────────────────────────────────────────────────────────────

@dataclass
class EnrichResult:
    path:         str
    success:      bool  = False
    merged_meta:  dict  = field(default_factory=dict)
    annotation:   dict  = field(default_factory=dict)
    review_item:  Optional[ReviewItem] = None
    wrote_tags:   bool  = False
    error:        Optional[str] = None


# ── tag writer ────────────────────────────────────────────────────────────────

def _write_tags(path: str, meta: dict) -> bool:
    """
    Write enriched tags back to the audio file using mutagen.

    Three independent phases so a failure in one never blocks the others:
      Phase 1 — easy-mode text tags (title, artist, album, genre, composer …)
      Phase 2 — cover art (format-specific low-level APIC / picture frame)
      Phase 3 — composer via low-level API (handles formats where easy fails
                 and doubles as the authoritative write for MP3 TCOM / M4A ©wrt)

    Returns True when at least one phase wrote successfully.
    """
    import mutagen

    wrote_any = False

    # ── Phase 1: easy-mode text tags ─────────────────────────────────────────
    try:
        audio = mutagen.File(path, easy=True)
        if audio is not None:
            if meta.get("title"):    audio["title"]       = [meta["title"]]
            if meta.get("artist"):   audio["artist"]      = [meta["artist"]]
            if meta.get("album"):    audio["album"]       = [meta["album"]]
            if meta.get("year"):     audio["date"]        = [str(meta["year"])]
            if meta.get("track"):    audio["tracknumber"] = [str(meta["track"])]
            if meta.get("genre"):    audio["genre"]       = [meta["genre"]]
            if meta.get("composer"):
                try:
                    audio["composer"] = [meta["composer"]]
                except (KeyError, ValueError):
                    pass   # key not in easy-map for this format; Phase 3 covers it
            audio.save()
            wrote_any = True
    except Exception:
        pass   # corrupt / unrecognised by easy-mode; Phases 2 & 3 still run

    # ── Phase 2: cover art (format-specific, always attempted) ───────────────
    if meta.get("art_bytes"):
        try:
            _write_art(path, meta["art_bytes"])
            wrote_any = True
        except Exception:
            pass

    # ── Phase 3: composer via low-level API (always attempted) ───────────────
    # This is the authoritative write for TCOM/©wrt.  It runs even when Phase 1
    # failed so classical tracks get their composer tag regardless.
    if meta.get("composer"):
        try:
            _write_composer(path, meta["composer"])
            wrote_any = True
        except Exception:
            pass

    return wrote_any


def _write_composer(path: str, composer: str) -> None:
    """Write composer tag using low-level mutagen API for each format."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".mp3":
            from mutagen.id3 import ID3, TCOM, error as ID3Error
            try:
                tags = ID3(path)
            except ID3Error:
                tags = ID3()
            tags.delall("TCOM")
            tags.add(TCOM(encoding=3, text=[composer]))
            tags.save(path)
        elif ext == ".flac":
            from mutagen.flac import FLAC
            f = FLAC(path)
            f["composer"] = [composer]
            f.save()
        elif ext in (".m4a", ".aac", ".mp4"):
            from mutagen.mp4 import MP4
            f = MP4(path)
            if f.tags is None:
                f.add_tags()
            f.tags["\xa9wrt"] = [composer]   # ©wrt — iTunes composer atom
            f.save()
        elif ext in (".ogg", ".opus", ".oga", ".spx"):
            # mutagen.File auto-detects OggVorbis vs OggOpus vs OggSpeex
            import mutagen
            f = mutagen.File(path)
            if f is not None:
                f["composer"] = [composer]
                f.save()
    except Exception:
        pass


def _write_art(path: str, art_bytes: bytes) -> None:
    """Write embedded cover art — MP3 / FLAC / M4A."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".mp3":
            from mutagen.id3 import ID3, APIC, error as ID3Error
            try:
                tags = ID3(path)
            except ID3Error:
                tags = ID3()
            tags.delall("APIC")
            tags.add(APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=art_bytes,
            ))
            tags.save(path)
        elif ext == ".flac":
            from mutagen.flac import FLAC, Picture
            f: Any = FLAC(path)
            pic = Picture()
            pic.type        = 3
            pic.mime        = "image/jpeg"
            pic.desc        = "Cover"
            pic.data        = art_bytes
            f.clear_pictures()
            f.add_picture(pic)
            f.save()
        elif ext in (".m4a", ".aac"):
            from mutagen.mp4 import MP4, MP4Cover
            f = MP4(path)
            if f.tags is None:
                f.add_tags()
            f.tags["covr"] = [MP4Cover(art_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
            f.save()
    except Exception:
        pass


# ── core pipeline ─────────────────────────────────────────────────────────────

def enrich_track(
    path:          str,
    api_key:       str,
    mb_client:     MusicBrainzClient,
    review_queue:  ReviewQueue,
    *,
    existing_meta: Optional[dict] = None,
    threshold:     float = 0.70,
    write_back:    bool  = True,
) -> EnrichResult:
    """
    Run the AcoustID → MusicBrainz enrichment pipeline for a single track.

    Parameters
    ----------
    path          Absolute path to the audio file.
    api_key       AcoustID application API key.
    mb_client     Shared MusicBrainzClient (handles rate limiting).
    review_queue  Items below *threshold* are pushed here for user review.
    existing_meta Current Library.meta_cache entry (avoids re-reading tags).
    threshold     Auto-accept if AcoustID score >= this value.
    write_back    If True, write enriched tags back to the file on disk.
    """
    result = EnrichResult(path=path)

    if not os.path.isfile(path):
        result.error = "file not found"
        return result

    # ── 1. fingerprint ────────────────────────────────────────────────────────
    try:
        fp_str, duration = fingerprint(path)
    except RuntimeError as exc:
        result.error = str(exc)
        return result
    except Exception as exc:
        result.error = f"fingerprint failed: {exc}"
        return result

    # ── 2. AcoustID lookup ────────────────────────────────────────────────────
    candidates = lookup_raw(api_key, fp_str, duration)
    if not candidates:
        result.error = "no AcoustID results"
        # Store fingerprint + explicit no-match flag so the daemon can schedule
        # a retry after acoustid_retry_after days instead of locking out forever.
        result.annotation = {
            "acoustid_fp":          fp_str,
            "acoustid_duration":    duration,
            "acoustid_no_match":    True,
            "acoustid_attempted_at": time.time(),
        }
        return result

    top = candidates[0]
    result.annotation["acoustid_score"]        = top.score
    result.annotation["acoustid_fp"]           = fp_str
    result.annotation["acoustid_attempted_at"] = time.time()

    # ── 3. confidence gate ────────────────────────────────────────────────────
    matched = best_match(candidates, threshold=threshold)

    if matched is None:
        # Below threshold — push to review queue for user action
        rec = top.best_recording
        review_queue.push(ReviewItem(
            path=path,
            original_meta=existing_meta or {},
            proposed_meta={
                "title":  rec.title  if rec else None,
                "artist": (rec.artists[0].get("name") if rec and rec.artists else None),
            },
            score=top.score,
            acoustid=top.acoustid,
            mbid=rec.mbid if rec else "",
        ))
        result.error = f"low confidence ({top.score:.2f}) — queued for review"
        return result

    # ── 4. MusicBrainz fetch ──────────────────────────────────────────────────
    rec       = matched.best_recording
    mb_record = None
    if rec and rec.mbid:
        mb_record = mb_client.fetch_recording(rec.mbid)

    if mb_record is None:
        result.error = "MusicBrainz fetch failed"
        return result

    # ── 5. build merged meta ──────────────────────────────────────────────────
    base  = dict(existing_meta or {})
    fresh = mb_record.as_meta_dict()
    # MB data wins over existing tags for all text fields except duration
    merged = {**base, **fresh}
    if base.get("duration"):         # preserve duration from audio file
        merged["duration"] = base["duration"]

    result.merged_meta = merged
    result.annotation.update(mb_record.as_annotation_dict())
    result.success = True

    # ── 6. optional write-back ────────────────────────────────────────────────
    if write_back:
        result.wrote_tags = _write_tags(path, merged)

    return result
