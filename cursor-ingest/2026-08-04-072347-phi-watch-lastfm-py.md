# phi / watch / lastfm.py

#source #python

> path: phi/watch/lastfm.py  
> ext: .py  

---

# phi / watch / lastfm.py

phi.watch.lastfm — Last.fm scrobbling.

Implements the Last.fm Scrobbling API v2.0 via plain urllib (no extra deps).

Scrobble rules (per Last.fm spec):
  · Track must have been playing for > 30 seconds  AND
  · Track must be > 240 seconds long  OR  > 50% complete

Usage
-----
    scrobbler = LastFmScrobbler(api_key, api_secret, session_key)
    scrobbler.now_playing(title, artist, album, duration)
    scrobbler.scrobble(title, artist, album, duration, timestamp)

First-launch auth (opens browser):
    url, token = LastFmScrobbler.get_auth_url(api_key)
    # user clicks Authorize in their brow

Defines: _sign, _call, get_auth_url, get_session, LastFmScrobbler, load_creds, save_creds, build_scrobbler, __init__, enabled, now_playing, scrobble, should_scrobble, _np, _sc

---

## Semantic links

→ [[engine-phi-player]]
→ [[scripts-embed-tracks]]
→ [[tools-enrich-c7]]
→ [[engine-phi-session]]
→ [[2026-07-21-000947-clean-the-entire-misc-folder-top-to-bottom]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-lastfm-meta-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-race-watcher-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-watcher-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-smart-playlist-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
