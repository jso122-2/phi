"""
tools.enrich_c7 — targeted metadata enrichment for cluster-7 gaps.

Two gap types
-------------
A. Named tracks with sparse/missing lfm_tags (9 tracks)
   → Hits Last.fm track.getInfo + artist.getTopTags fallback
   → Requires: LASTFM_API_KEY env var (or --lfm-key arg)

B. Stem-only tracks with no artist/name (26 tracks, YouTube IDs)
   → AcoustID fingerprint via fpcalc → MusicBrainz lookup → identity
   → Requires: fpcalc on PATH (brew install chromaprint) + ACOUSTID_KEY env

Run
---
    # Named tracks (Last.fm):
    LASTFM_API_KEY=<your_key> python -m tools.enrich_c7

    # Stem-only (AcoustID):
    ACOUSTID_KEY=<your_key> python -m tools.enrich_c7 --mode acoustid

    # Both:
    LASTFM_API_KEY=<key> ACOUSTID_KEY=<key> python -m tools.enrich_c7 --mode all

    # Dry run — show what would be patched, no writes:
    python -m tools.enrich_c7 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

CLUSTER_MAP = Path(__file__).parent.parent / "models" / "cluster_out" / "cluster_map.json"
LIB = Path("/Users/a0/Documents/misc/Spotify/Liked Songs")
AUDIO_EXTS = frozenset({".mp3", ".flac", ".wav", ".m4a", ".ogg"})

_LFM_API   = "https://ws.audioscrobbler.com/2.0/"
_AID_API   = "https://api.acoustid.org/v2/lookup"
_TIMEOUT   = 12
_MAX_TAGS  = 7


# ── helpers ───────────────────────────────────────────────────────────────────

def _api_get(url: str, params: dict, headers: dict | None = None) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        full,
        headers=headers or {"User-Agent": "spotify-rip/1.0 enrich_c7"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"_error": str(e)}


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    m = re.match(r"([^.!?]+[.!?])", text)
    return m.group(1).strip() if m else text[:300]


# ── identify gap tracks ───────────────────────────────────────────────────────

def _identify_gaps() -> tuple[list[dict], list[dict]]:
    """Return (named_sparse, stem_only) lists from the library."""
    if not CLUSTER_MAP.exists():
        raise FileNotFoundError(f"cluster_map not found: {CLUSTER_MAP}")
    with CLUSTER_MAP.open() as f:
        cmap = json.load(f)
    c7 = {name for name, cl in cmap.items() if cl == 7}

    named_sparse: list[dict] = []
    stem_only:    list[dict] = []

    for audio in sorted(LIB.iterdir()):
        if audio.suffix.lower() not in AUDIO_EXTS:
            continue
        j = audio.with_suffix(".json")
        if not j.exists():
            continue
        with j.open() as f:
            d = json.load(f)

        artist = d.get("artist", "")
        name   = d.get("name", "")
        display = f"{artist} — {name}" if artist and name else audio.stem

        if display not in c7:
            continue

        tags = (
            d.get("lfm_tags", []) +
            d.get("discogs_genre", []) +
            d.get("discogs_style", [])
        )
        if d.get("itunes_genre"):
            tags.append(d["itunes_genre"])
        # flatten any accidentally nested lists
        flat_tags = [t for t in tags if isinstance(t, str)]

        if not artist and not name:
            stem_only.append({
                "stem": audio.stem,
                "audio": str(audio),
                "json": str(j),
                "data": d,
            })
        elif len(flat_tags) <= 2:
            named_sparse.append({
                "artist": artist,
                "name": name,
                "spotify_id": d.get("spotify_id", ""),
                "audio": str(audio),
                "json": str(j),
                "current_tags": flat_tags,
                "data": d,
            })

    return named_sparse, stem_only


# ── Last.fm enrichment ────────────────────────────────────────────────────────

def _lfm_track_info(artist: str, title: str, key: str) -> Optional[dict]:
    data = _api_get(_LFM_API, {
        "method": "track.getInfo",
        "track": title,
        "artist": artist,
        "autocorrect": "1",
        "api_key": key,
        "format": "json",
    })
    track = data.get("track")
    if not track or isinstance(track, str):
        return None

    listeners = int(track.get("listeners") or 0)
    playcount  = int(track.get("playcount") or 0)
    tag_list   = (track.get("toptags") or {}).get("tag", [])
    if isinstance(tag_list, dict):
        tag_list = [tag_list]
    tags = [t["name"] for t in tag_list[:_MAX_TAGS]
            if isinstance(t, dict) and t.get("name")]

    wiki_raw = (track.get("wiki") or {}).get("summary", "")
    result: dict = {
        "lfm_listeners": listeners,
        "lfm_playcount": playcount,
        "lfm_tags": tags,
    }
    if wiki_raw:
        result["lfm_wiki"] = _strip_html(wiki_raw)

    mb_rec = (track.get("mbid") or "").strip()
    if mb_rec:
        result["mb_recording_id"] = mb_rec

    return result


def _lfm_artist_tags(artist: str, key: str) -> list[str]:
    data = _api_get(_LFM_API, {
        "method": "artist.getTopTags",
        "artist": artist,
        "autocorrect": "1",
        "api_key": key,
        "format": "json",
    })
    tag_list = (data.get("toptags") or {}).get("tag", [])
    if isinstance(tag_list, dict):
        tag_list = [tag_list]
    return [t["name"] for t in tag_list[:_MAX_TAGS]
            if isinstance(t, dict) and t.get("name")]


def enrich_named(
    named: list[dict],
    lfm_key: str,
    dry_run: bool = False,
) -> list[dict]:
    results = []
    for track in named:
        artist = track["artist"]
        name   = track["name"]
        print(f"  [lfm] {artist} — {name}")

        info = _lfm_track_info(name, artist, lfm_key)
        time.sleep(0.5)

        # artist fallback: fires when track not found OR found but has no tags
        if not info or not info.get("lfm_tags"):
            artist_tags = _lfm_artist_tags(artist, lfm_key)
            time.sleep(0.5)
            if artist_tags:
                if info is None:
                    info = {}
                info["lfm_tags"] = artist_tags
                print(f"       → artist fallback: {artist_tags}")

        if not info:
            print(f"       ✗ no data returned")
            results.append({**track, "enriched": False, "new_tags": []})
            continue

        new_tags = info.get("lfm_tags", [])
        print(f"       ✓ tags: {new_tags}")

        if not dry_run:
            d = track["data"]
            d.update({k: v for k, v in info.items() if v})
            if "lastfm" not in d.get("_sources", []):
                d.setdefault("_sources", []).append("lastfm_re")
            with open(track["json"], "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)

        results.append({**track, "enriched": bool(new_tags), "new_tags": new_tags})

    return results


# ── AcoustID / fpcalc enrichment ──────────────────────────────────────────────

_FPCALC_PATHS = [
    "/opt/homebrew/bin/fpcalc",
    "/usr/local/bin/fpcalc",
    "fpcalc",
]


def _fpcalc_bin() -> Optional[str]:
    for p in _FPCALC_PATHS:
        try:
            if subprocess.run([p], capture_output=True).returncode in (0, 2):
                return p
        except FileNotFoundError:
            continue
    return None


def _fpcalc(audio_path: str) -> Optional[tuple[int, str]]:
    """Run fpcalc and return (duration_int, fingerprint) or None."""
    bin_ = _fpcalc_bin()
    if not bin_:
        return None
    try:
        out = subprocess.check_output(
            [bin_, audio_path],
            timeout=60,
            stderr=subprocess.DEVNULL,
        ).decode()
        duration, fingerprint = None, None
        for line in out.strip().splitlines():
            if line.startswith("DURATION="):
                duration = int(float(line.split("=", 1)[1]))
            elif line.startswith("FINGERPRINT="):
                fingerprint = line.split("=", 1)[1]
        if duration is not None and fingerprint:
            return duration, fingerprint
        return None
    except Exception:
        return None


def _acoustid_lookup(duration: int, fingerprint: str, key: str) -> Optional[dict]:
    """POST to AcoustID — fingerprints are too long for GET URLs."""
    params = urllib.parse.urlencode({
        "client": key,
        "duration": str(duration),
        "fingerprint": fingerprint,
        "meta": "recordings+releasegroups",
    }).encode("utf-8")
    req = urllib.request.Request(
        _AID_API,
        data=params,
        headers={
            "User-Agent": "spotify-rip/1.0 enrich_c7",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"_error": str(e)}

    results = data.get("results", [])
    if not results:
        return None
    best = max(results, key=lambda r: r.get("score", 0))
    if best.get("score", 0) < 0.6:
        return None
    recs = best.get("recordings", [])
    if not recs:
        return None
    rec = recs[0]
    artists = rec.get("artists", [])
    return {
        "name": rec.get("title", ""),
        "artist": artists[0].get("name", "") if artists else "",
        "mb_recording_id": rec.get("id", ""),
        "_acoustid_score": best["score"],
    }


_YT_OEMBED = "https://www.youtube.com/oembed"


def _yt_oembed(yt_id: str) -> Optional[dict]:
    """
    Fetch YouTube oEmbed for a video ID — no API key required.
    Returns {"title": ..., "author_name": ...} or None.
    """
    params = urllib.parse.urlencode({
        "url": f"https://www.youtube.com/watch?v={yt_id}",
        "format": "json",
    })
    req = urllib.request.Request(
        f"{_YT_OEMBED}?{params}",
        headers={"User-Agent": "spotify-rip/1.0 enrich_c7"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _parse_yt_title(title: str, channel: str) -> tuple[str, str]:
    """
    Best-effort parse of 'Artist - Track Title' from a YouTube title.
    Falls back to (channel, title) if no separator found.
    """
    for sep in (" - ", " – ", " — ", " | "):
        if sep in title:
            parts = title.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return channel.strip(), title.strip()


def enrich_stems(
    stems: list[dict],
    acoustid_key: str,
    dry_run: bool = False,
) -> list[dict]:
    """
    Identify stem-only (YouTube ID) tracks via:
      1. YouTube oEmbed  → video title + channel (no key needed)
      2. Parse title into artist / track name
      3. Last.fm track.getInfo  → lfm_tags (uses LASTFM_API_KEY if set)
    AcoustID is tried as an additional signal when a key is provided,
    but YouTube oEmbed is the primary path for YouTube-sourced files.
    """
    lfm_key = os.environ.get("LASTFM_API_KEY", "")
    results = []

    for track in stems:
        stem = track["stem"]
        print(f"  [yt→lfm] {stem}")

        # ── Step 1: YouTube oEmbed ────────────────────────────────────────────
        oembed = _yt_oembed(stem)
        if not oembed:
            print(f"           ✗ YouTube oEmbed failed (video unavailable or private)")
            results.append({**track, "enriched": False, "reason": "yt_unavailable"})
            continue

        yt_title   = oembed.get("title", "")
        yt_channel = oembed.get("author_name", "")
        print(f"           YT: '{yt_title}' by '{yt_channel}'")

        artist, name = _parse_yt_title(yt_title, yt_channel)

        # ── Step 2: Last.fm lookup with parsed identity ───────────────────────
        lfm_result: dict = {}
        if lfm_key and artist and name:
            info = _lfm_track_info(name, artist, lfm_key)
            time.sleep(0.5)
            if info:
                lfm_result = info
            if not lfm_result.get("lfm_tags") and artist:
                artist_tags = _lfm_artist_tags(artist, lfm_key)
                time.sleep(0.5)
                if artist_tags:
                    lfm_result["lfm_tags"] = artist_tags

        tags = lfm_result.get("lfm_tags", [])
        print(f"           → artist='{artist}'  name='{name}'  tags={tags}")

        if not dry_run:
            d = track["data"]
            d["name"]   = name
            d["artist"] = artist
            d["_yt_title"]   = yt_title
            d["_yt_channel"] = yt_channel
            if lfm_result:
                d.update({k: v for k, v in lfm_result.items() if v})
            sources = d.get("_sources", [])
            if "youtube_oembed" not in sources:
                sources.append("youtube_oembed")
            d["_sources"] = sources
            with open(track["json"], "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)

        results.append({
            **track,
            "enriched": bool(name),
            "identity": {"artist": artist, "name": name, "yt_title": yt_title},
            "new_tags": tags,
        })

    return results


# ── report ────────────────────────────────────────────────────────────────────

def _print_report(named_results: list[dict], stem_results: list[dict]) -> None:
    n_lfm_ok  = sum(1 for r in named_results if r.get("enriched"))
    n_aid_ok  = sum(1 for r in stem_results if r.get("enriched"))

    print()
    print("=" * 60)
    print("ENRICHMENT REPORT")
    print("=" * 60)
    print(f"Named / sparse-tag tracks:  {n_lfm_ok}/{len(named_results)} enriched via Last.fm")
    print(f"Stem-only tracks:           {n_aid_ok}/{len(stem_results)} identified via AcoustID")
    print()

    if named_results:
        print("Named track results:")
        for r in named_results:
            mark = "✓" if r.get("enriched") else "✗"
            tags = r.get("new_tags", [])[:4]
            print(f"  {mark} {r['artist']} — {r['name']}")
            if tags:
                print(f"      tags: {tags}")

    if stem_results:
        print()
        print("Stem-only results:")
        for r in stem_results:
            mark = "✓" if r.get("enriched") else "✗"
            reason = r.get("reason", "")
            identity = r.get("identity", {})
            tags = r.get("new_tags", [])[:3]
            if identity and identity.get("name"):
                tag_str = f"  tags={tags}" if tags else ""
                print(f"  {mark} {r['stem']} → {identity['artist']} — {identity['name']}{tag_str}")
            else:
                print(f"  {mark} {r['stem']} ({reason})")

    still_unknown = [r["stem"] for r in stem_results if not r.get("enriched")]
    if still_unknown:
        print()
        print(f"{len(still_unknown)} stems still unidentified — require manual lookup:")
        for s in still_unknown[:10]:
            print(f"  {s}")
        if len(still_unknown) > 10:
            print(f"  ... and {len(still_unknown) - 10} more")

    print()
    unid_path = Path(__file__).parent.parent / "models" / "cluster_out" / "unidentified_stems.json"
    if still_unknown:
        with open(unid_path, "w") as f:
            json.dump(still_unknown, f, indent=2)
        print(f"Unidentified stems list → {unid_path}")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich cluster-7 metadata gaps")
    parser.add_argument("--mode", choices=["lastfm", "acoustid", "all"], default="all")
    parser.add_argument("--lfm-key", default=os.environ.get("LASTFM_API_KEY", ""))
    parser.add_argument("--acoustid-key", default=os.environ.get("ACOUSTID_KEY", ""))
    parser.add_argument("--dry-run", action="store_true", help="no writes to disk")
    args = parser.parse_args()

    print("[enrich_c7] scanning cluster-7 gaps …")
    named, stems = _identify_gaps()
    print(f"  named sparse-tag: {len(named)}")
    print(f"  stem-only:        {len(stems)}")

    named_results: list[dict] = []
    stem_results:  list[dict] = []

    if args.mode in ("lastfm", "all"):
        if args.lfm_key:
            print(f"\n[enrich_c7] Last.fm enrichment (rate: 2 req/s) …")
            named_results = enrich_named(named, args.lfm_key, dry_run=args.dry_run)
        else:
            print("\n[enrich_c7] LASTFM_API_KEY not set — skipping named tracks")
            print("  Get a free key at https://www.last.fm/api/account/create")
            named_results = [{**t, "enriched": False, "new_tags": [], "reason": "no_key"} for t in named]

    if args.mode in ("acoustid", "all"):
        print(f"\n[enrich_c7] AcoustID fingerprinting …")
        stem_results = enrich_stems(stems, args.acoustid_key, dry_run=args.dry_run)

    _print_report(named_results, stem_results)

    if args.dry_run:
        print("(dry-run — no files written)")


if __name__ == "__main__":
    main()
