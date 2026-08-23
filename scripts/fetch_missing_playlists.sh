#!/usr/bin/env bash
# fetch_missing_playlists.sh — download all playlists that have no audio files yet
# Uses spotdl with the credentials in ~/.spotdl/config.json
# Run from any directory. Output lands in Playlists/<spotify_id>/

set -euo pipefail

SPOTDL="mamba run -n spotify-rip spotdl"
BASE="/Users/a0/Documents/misc/Spotify/Playlists"
LOG="$BASE/fetch_missing.log"

# Playlists to fetch: id | name
declare -A PLAYLISTS=(
    ["0fatjImBjowRpkWMINHr1M"]="14/5/25 IDM"
    ["1R1NOc3v5m173wRVRvMTze"]="Baby Driver (Music from the Motion Picture)"
    ["2ctUy4MBoO8i0y6EJYcqA5"]="Lazy Moon"
    ["2mRVAXyoLU0qdU1E5WpAyh"]="My Playlist #55"
    ["32jotkpCly7q9wQvu6uSeW"]="Unknown Pleasures"
    ["36VQ4ep6XxwnPVgPFBct5I"]="In The Court Of The Crimson King"
    ["Gil #201"]=""
)

echo "=== fetch_missing_playlists.sh ===" | tee -a "$LOG"
echo "Started: $(date)" | tee -a "$LOG"

for pid in "${!PLAYLISTS[@]}"; do
    name="${PLAYLISTS[$pid]}"
    dir="$BASE/$pid"
    mkdir -p "$dir"
    url="https://open.spotify.com/playlist/$pid"

    echo "" | tee -a "$LOG"
    echo "--- $name [$pid] ---" | tee -a "$LOG"
    echo "  → $dir" | tee -a "$LOG"

    $SPOTDL download "$url" \
        --output "$dir/{artists} - {title}.{output-ext}" \
        --format mp3 \
        --bitrate 128k \
        --overwrite skip \
        --threads 4 \
        2>&1 | tee -a "$LOG"
done

echo "" | tee -a "$LOG"
echo "Done: $(date)" | tee -a "$LOG"
