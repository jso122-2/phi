#!/usr/bin/env bash
# install_rsync_bridge.sh — install and start the samba rsync bridge daemon
#
# Usage:
#   ./install_rsync_bridge.sh          # install + start
#   ./install_rsync_bridge.sh stop     # stop and unload
#   ./install_rsync_bridge.sh restart  # reload
#   ./install_rsync_bridge.sh status   # check if running
#   ./install_rsync_bridge.sh logs     # tail live logs

set -euo pipefail

LABEL="com.samba-gnn.rsync-bridge"
PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.samba-gnn.rsync-bridge.plist"
AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_DST="$AGENTS_DIR/$LABEL.plist"
LOG_DIR="$(cd "$(dirname "$0")" && pwd)/logs"

# ── Helpers ───────────────────────────────────────────────────────────────────

info()  { echo "  [bridge] $*"; }
ok()    { echo "  ✓ $*"; }
err()   { echo "  ✗ $*" >&2; exit 1; }

# ── Commands ──────────────────────────────────────────────────────────────────

cmd_install() {
    mkdir -p "$AGENTS_DIR" "$LOG_DIR"

    if [ ! -f "$PLIST_SRC" ]; then
        err "Plist not found: $PLIST_SRC"
    fi

    cp "$PLIST_SRC" "$PLIST_DST"
    ok "Copied plist → $PLIST_DST"

    # Unload any existing instance first
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    launchctl load -w "$PLIST_DST"
    ok "Daemon loaded and started"
    echo ""
    echo "  Logs:  tail -f $LOG_DIR/rsync_bridge.log"
    echo "  Status: $0 status"
    echo "  Stop:   $0 stop"
}

cmd_stop() {
    launchctl unload "$PLIST_DST" 2>/dev/null && ok "Daemon stopped" || info "Not running"
}

cmd_restart() {
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    cp "$PLIST_SRC" "$PLIST_DST"
    sleep 1
    launchctl load -w "$PLIST_DST"
    ok "Daemon restarted"
}

cmd_status() {
    LINE=$(launchctl list | grep -F "$LABEL" || true)
    if [ -z "$LINE" ]; then
        info "Not loaded"
        return
    fi
    PID=$(echo "$LINE" | awk '{print $1}')
    EXIT=$(echo "$LINE" | awk '{print $2}')
    if [ "$PID" = "-" ]; then
        info "Loaded but not running (last exit=$EXIT)"
    else
        ok "Running (pid=$PID, last_exit=$EXIT)"
    fi
}

cmd_logs() {
    trap 'exit 0' INT
    # Python logging → stderr (rsync_bridge.log); stdout → rsync_bridge_out.log
    tail -f "$LOG_DIR/rsync_bridge.log" 2>/dev/null
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

CMD="${1:-install}"
case "$CMD" in
    install)  cmd_install ;;
    stop)     cmd_stop ;;
    restart)  cmd_restart ;;
    status)   cmd_status ;;
    logs)     cmd_logs ;;
    *)        echo "Usage: $0 [install|stop|restart|status|logs]"; exit 1 ;;
esac
