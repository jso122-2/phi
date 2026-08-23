# phi / core / smart_playlist.py

#source #python

> path: phi/core/smart_playlist.py  
> ext: .py  

---

# phi / core / smart_playlist.py

phi.core.smart_playlist — rule-based playlist generator.

DSL syntax (rules are space-separated; all are ANDed together):

    bpm:120-130          BPM in range [120, 130]
    bpm:>=120            BPM >= 120
    bpm:<=130            BPM <= 130
    rating:>=3           star rating >= 3
    rating:5             exactly 5 stars
    plays:>=10           played 10+ times
    plays:0              never played
    never-heard          alias for plays:0
    artist:reznor        artist field contains "reznor" (case-insensitive)
    album:social         album field contains "social"
    genre:electronic

Defines: _num_predicate, _parse_num_expr, _parse_date_expr, parse_rules, SmartPlaylist, _sort_results, __post_init__, evaluate, as_dict, from_dict, _bpm_rule, _rating_rule, _plays_rule, _dur_rule, _added_rule, _artist_rule, _album_rule, _genre_rule, _mood_rule, _key_rule, _energy_rule, _completion_rule, _skip_rule, _mins_rule, _secs_rule, _elo_rule

---

## Semantic links

→ [[engine-phi-player]]
→ [[scripts-embed-tracks]]
→ [[mcp-server]]
→ [[pipeline-sources-youtube-music]]
→ [[scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-playlist-store-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-library-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-playlist-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-queue-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
