# -*- coding: utf-8 -*-
"""phi.meta.lastfm_meta — read metadata FROM Last.fm (separate from scrobbling).

Reads track info, user tags, and similar tracks from the Last.fm API.
Uses only the public read API — no session key or scrobbling credentials needed.
All calls are over plain urllib (no extra deps).

Data returned per track
-----------------------
listeners       int     Global unique listener count
playcount       int     Total global scrobble count
tags            list[str]  Top community tags (max 5) — rich genre / mood labels
wiki_summary    str     Short Wikipedia-style blurb (first sentence only)
similar_tracks  list[dict]  Up to 5 similar tracks {title, artist, match}

Setup (phi_config.yaml)
-----------------------
meta_enrichment:
  lastfm_api_key: "YOUR_API_KEY"   # read-only key, free at https://www.last.fm/api

The same key used for scrobbling works here.
If no key is configured, all calls return None silently.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


_API_URL = "https://ws.audioscrobbler.com/2.0/"
_TIMEOUT = 8


# ── result type ───────────────────────────────────────────────────────────────

@dataclass
class LastFmTrackInfo:
    title:         str
    artist:        str
    listeners:     int           = 0
    playcount:     int           = 0
    tags:          list[str]     = field(default_factory=list)   # top community tags
    wiki_summary:  Optional[str] = None
    similar:       list[dict]    = field(default_factory=list)   # {title, artist, match}

    def as_annotation_dict(self) -> dict:
        d: dict = {
            "lfm_listeners":  self.listeners,
            "lfm_playcount":  self.playcount,
            "lfm_tags":       self.tags,
            "lfm_enriched":   True,
        }
        if self.wiki_summary:
            d["lfm_wiki"] = self.wiki_summary
        if self.similar:
            d["lfm_similar"] = self.similar
        return d

    @property
    def top_tag(self) -> Optional[str]:
        """Return the most popular community tag, or None."""
        return self.tags[0] if self.tags else None


# ── low-level API call ────────────────────────────────────────────────────────

def _api_get(method: str, params: dict, api_key: str) -> dict:
    """Make a read-only GET call to the Last.fm API."""
    p = {
        "method":  method,
        "api_key": api_key,
        "format":  "json",
        **params,
    }
    url = _API_URL + "?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(
        url, headers={"User-Agent": "phi/1.0 (local music player)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return {}


def _strip_html(text: str) -> str:
    """Remove HTML tags and condense whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Trim to first sentence for brevity
    m = re.match(r"([^.!?]+[.!?])", text)
    return m.group(1).strip() if m else text[:200]


# ── public fetch functions ────────────────────────────────────────────────────

def fetch_track_info(
    title:   str,
    artist:  str,
    api_key: str,
    *,
    autocorrect: bool = True,
) -> Optional[LastFmTrackInfo]:
    """
    Fetch track info from Last.fm (listeners, playcount, tags, wiki).

    Parameters
    ----------
    title       Track title.
    artist      Artist name.
    api_key     Last.fm read API key.
    autocorrect If True, Last.fm corrects minor spelling errors.

    Returns LastFmTrackInfo on success, None on failure.
    """
    if not (api_key and title and artist):
        return None

    data = _api_get(
        "track.getInfo",
        {
            "track":       title,
            "artist":      artist,
            "autocorrect": "1" if autocorrect else "0",
        },
        api_key,
    )

    track = data.get("track")
    if not track or isinstance(track, str):
        return None

    listeners = int(track.get("listeners") or 0)
    playcount = int(track.get("playcount") or 0)

    # Community tags (sorted by weight, descending)
    tag_list = (track.get("toptags") or {}).get("tag", [])
    if isinstance(tag_list, dict):
        tag_list = [tag_list]
    tags = [t["name"] for t in tag_list[:5] if isinstance(t, dict) and t.get("name")]

    # Wiki summary — first sentence only
    wiki_raw = (track.get("wiki") or {}).get("summary", "")
    wiki = _strip_html(wiki_raw) if wiki_raw else None

    # Similar tracks — included in track.getInfo under similarartists if requested
    # (We get similar tracks from a separate call for better coverage)
    similar = fetch_similar_tracks(title, artist, api_key, limit=5)

    return LastFmTrackInfo(
        title        = track.get("name") or title,
        artist       = (track.get("artist") or {}).get("name", artist) if isinstance(track.get("artist"), dict) else artist,
        listeners    = listeners,
        playcount    = playcount,
        tags         = tags,
        wiki_summary = wiki,
        similar      = similar,
    )


def fetch_similar_tracks(
    title:   str,
    artist:  str,
    api_key: str,
    *,
    limit: int = 5,
) -> list[dict]:
    """
    Fetch similar tracks from Last.fm.

    Returns a list of dicts: [{title, artist, match}, …]
    where match is a 0–1 similarity score.
    """
    if not (api_key and title and artist):
        return []

    data = _api_get(
        "track.getSimilar",
        {
            "track":       title,
            "artist":      artist,
            "limit":       str(limit),
            "autocorrect": "1",
        },
        api_key,
    )

    tracks = (data.get("similartracks") or {}).get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]

    result = []
    for t in tracks[:limit]:
        if not isinstance(t, dict):
            continue
        artist_obj = t.get("artist", {})
        result.append({
            "title":  t.get("name", ""),
            "artist": artist_obj.get("name", "") if isinstance(artist_obj, dict) else str(artist_obj),
            "match":  float(t.get("match", 0.0)),
        })
    return result


def fetch_artist_tags(
    artist:  str,
    api_key: str,
    *,
    limit: int = 5,
) -> list[str]:
    """
    Fetch top tags for an artist.  Useful for genre enrichment when
    track-level tags are sparse.
    """
    if not (api_key and artist):
        return []
    data = _api_get(
        "artist.getTopTags",
        {"artist": artist, "autocorrect": "1"},
        api_key,
    )
    tag_list = (data.get("toptags") or {}).get("tag", [])
    if isinstance(tag_list, dict):
        tag_list = [tag_list]
    return [t["name"] for t in tag_list[:limit] if isinstance(t, dict) and t.get("name")]


# ── module-level helper ───────────────────────────────────────────────────────

def get_lastfm_api_key() -> str:
    """Return the Last.fm read API key from phi_config.yaml."""
    try:
        from phi.config import load_phi_config
        cfg = load_phi_config()
        # Accept key from either meta_enrichment or top-level lastfm block
        key = (
            cfg.get("meta_enrichment", {}).get("lastfm_api_key", "")
            or cfg.get("lastfm", {}).get("api_key", "")
        )
        return key or ""
    except Exception:
        return ""
