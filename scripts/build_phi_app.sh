#!/usr/bin/env bash
# scripts/build_phi_app.sh — build phi.app
#
# Creates a thin macOS application bundle that wraps the phi Python package.
# The bundle gives phi a proper macOS identity (Cmd+Tab, Dock, Spotlight)
# without bundling Python or any dependencies.
#
# Usage:
#   bash scripts/build_phi_app.sh              # builds phi.app in project root
#   bash scripts/build_phi_app.sh --install    # also copies to ~/Applications
#
# Requirements: micromamba / conda, spotify-rip env already created.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_NAME="phi"
APP_DIR="$REPO_ROOT/$APP_NAME.app"

# ── Find the spotify-rip Python ───────────────────────────────────────────────
_find_python() {
    local candidates=(
        "/opt/homebrew/Cellar/micromamba/2.8.1/envs/spotify-rip/bin/python"
        "$HOME/.local/share/mamba/envs/spotify-rip/bin/python"
        "$HOME/miniforge3/envs/spotify-rip/bin/python"
        "$HOME/mambaforge/envs/spotify-rip/bin/python"
        "$HOME/miniconda3/envs/spotify-rip/bin/python"
        "$HOME/anaconda3/envs/spotify-rip/bin/python"
    )
    for p in "${candidates[@]}"; do
        [[ -x "$p" ]] && echo "$p" && return
    done
    # fallback: search
    local found
    found="$(find /opt /Users -name "python" -path "*/spotify-rip/bin/*" 2>/dev/null | head -1)"
    [[ -n "$found" && -x "$found" ]] && echo "$found" && return
    echo ""
}

PYTHON_BIN="$(_find_python)"
if [[ -z "$PYTHON_BIN" ]]; then
    echo "ERROR: spotify-rip Python not found."
    echo "       Run: mamba env create -f environment.yml"
    exit 1
fi

echo "phi.app builder"
echo "  Python : $PYTHON_BIN"
echo "  Repo   : $REPO_ROOT"
echo "  Output : $APP_DIR"
echo ""

# ── Build bundle structure ────────────────────────────────────────────────────
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"

# ── Icon ──────────────────────────────────────────────────────────────────────
ICNS_SRC="$REPO_ROOT/phi/resources/phi.icns"
if [[ -f "$ICNS_SRC" ]]; then
    cp "$ICNS_SRC" "$APP_DIR/Contents/Resources/phi.icns"
    ICON_KEY='
    <key>CFBundleIconFile</key>
    <string>phi</string>'
else
    echo "  (no icon — phi/resources/phi.icns not found)"
    ICON_KEY=""
fi

# ── Info.plist ────────────────────────────────────────────────────────────────
cat > "$APP_DIR/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>phi</string>
$ICON_KEY
    <key>CFBundleIdentifier</key>
    <string>local.phi.musicplayer</string>

    <key>CFBundleName</key>
    <string>phi</string>

    <key>CFBundleDisplayName</key>
    <string>φ</string>

    <key>CFBundlePackageType</key>
    <string>APPL</string>

    <key>CFBundleVersion</key>
    <string>1.0.0</string>

    <key>CFBundleShortVersionString</key>
    <string>1.0</string>

    <key>NSHighResolutionCapable</key>
    <true/>

    <key>NSPrincipalClass</key>
    <string>NSApplication</string>

    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>

    <key>NSHumanReadableCopyright</key>
    <string>phi music player</string>

    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
</dict>
</plist>
PLIST

# ── Launcher (Contents/MacOS/phi) ─────────────────────────────────────────────
# We embed the absolute Python path so the launcher works when opened from
# Finder / Spotlight where PATH is minimal and conda is not activated.
# exec replaces the shell process with Python; macOS retains the bundle
# identity because the process was spawned from within the .app bundle.
cat > "$APP_DIR/Contents/MacOS/phi" << LAUNCHER
#!/usr/bin/env bash
# phi.app launcher — do not edit by hand; regenerate with scripts/build_phi_app.sh
PYTHON="$PYTHON_BIN"
REPO="$REPO_ROOT"

if [[ ! -x "\$PYTHON" ]]; then
    osascript -e 'display alert "phi — launch failed" message "Python not found at the expected path.\n\nRegenerate the app bundle:\n  bash scripts/build_phi_app.sh" as critical buttons {"OK"} default button "OK"'
    exit 1
fi

cd "\$REPO"
exec "\$PYTHON" -m phi "\$@"
LAUNCHER

chmod +x "$APP_DIR/Contents/MacOS/phi"

echo "✓ Built: $APP_DIR"

# ── Optional install ──────────────────────────────────────────────────────────
if [[ "${1:-}" == "--install" ]]; then
    TARGET="$HOME/Applications/$APP_NAME.app"
    mkdir -p "$HOME/Applications"
    rm -rf "$TARGET"
    cp -r "$APP_DIR" "$TARGET"
    echo "✓ Installed to: $TARGET"
    echo ""
    echo "You can now launch phi from Spotlight, Finder, or the Dock."
    echo "Cmd+Tab will show it as 'phi' (φ)."
fi

echo ""
echo "To install into ~/Applications:"
echo "  bash scripts/build_phi_app.sh --install"
echo ""
echo "To launch directly:"
echo "  open $APP_DIR"
