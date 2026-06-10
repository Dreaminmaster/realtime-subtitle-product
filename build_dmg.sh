#!/bin/bash
# =============================================================================
# DMG Packaging Script for Realtime Subtitle
#
# Creates a self-contained .app bundle with its own Python venv.
# The venv is inside the .app — no system Python contamination.
#
# Usage:  bash build_dmg.sh [version]
# =============================================================================
set -e

VERSION="${1:-1.0.0}"
APP_NAME="RealtimeSubtitle"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
APP_BUNDLE="${BUILD_DIR}/${APP_NAME}.app"
CONTENTS="${APP_BUNDLE}/Contents"
MACOS_DIR="${CONTENTS}/MacOS"
RESOURCES="${CONTENTS}/Resources"
VENV_DIR="${RESOURCES}/venv"
DIST_DIR="${SCRIPT_DIR}/dist"

echo "============================================"
echo "  Building ${APP_NAME} v${VERSION}"
echo "============================================"
echo ""

# ---- Clean ----
rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${MACOS_DIR}" "${RESOURCES}" "${DIST_DIR}"

# ---- Step 1: Create venv inside the app bundle ----
echo "[1/6] Creating Python venv inside .app bundle..."
python3 -m venv "${VENV_DIR}" 2>&1 || {
    echo "ERROR: python3 not found. Please install Python 3.10+ from python.org"
    exit 1
}
echo "  venv created at: ${VENV_DIR}"

# ---- Step 2: Install dependencies into the venv ----
echo "[2/6] Installing Python dependencies into venv..."
"${VENV_DIR}/bin/python3" -m pip install --no-cache-dir --upgrade pip 2>&1

# Install packages: try each individually so one failure doesn't block all
echo "  Installing from requirements.txt..."
FAILED_PKGS=""
while IFS= read -r line; do
    # Skip comments and empty lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue
    echo "    → $line"
    if "${VENV_DIR}/bin/python3" -m pip install --no-cache-dir "$line" 2>&1; then
        echo "      ✓ installed"
    else
        echo "      ✗ FAILED (may be macOS-only or optional)"
        FAILED_PKGS="${FAILED_PKGS}  - ${line%%;*}"$'\n'
    fi
done < "${SCRIPT_DIR}/requirements.txt"

if [ -n "$FAILED_PKGS" ]; then
    echo ""
    echo "  ⚠️  Some packages failed to install:"
    echo "$FAILED_PKGS"
    echo "  (This is normal if building on Linux — DMG must be built on macOS)"
fi
echo "  Dependencies check complete."

# ---- Step 3: Copy project files into Resources ----
echo "[3/6] Copying project files..."
rsync -av --exclude='.git' \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='build' \
      --exclude='dist' \
      --exclude='transcripts' \
      --exclude='.DS_Store' \
      --exclude='*.dmg' \
      --exclude='venv' \
      "${SCRIPT_DIR}/" "${RESOURCES}/" 2>/dev/null

# Mark deps installed so launcher doesn't try again
touch "${RESOURCES}/.deps_installed"

echo "  Files copied to: ${RESOURCES}"

# ---- Step 4: Create launcher script ----
echo "[4/6] Creating launcher script..."
cat > "${MACOS_DIR}/realtime-subtitle" << 'LAUNCHER'
#!/bin/bash
# =============================================================================
# Realtime Subtitle Launcher
# Runs the app using its bundled Python venv (fully self-contained).
# =============================================================================

# Resolve real script location (follows symlinks)
while [ -h "$0" ]; do
    DIR="$(cd -P "$(dirname "$0")" && pwd)"
    SCRIPT="$(readlink "$0")"
    [[ "$SCRIPT" != /* ]] && SCRIPT="$DIR/$SCRIPT"
done
APP_DIR="$(cd -P "$(dirname "$0")/../.." && pwd)"
RESOURCES="${APP_DIR}/Contents/Resources"
VENV_PYTHON="${RESOURCES}/venv/bin/python3"

cd "$RESOURCES"

# If bundled venv not available, fall back to system Python
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Bundled Python venv not found at $VENV_PYTHON"
    echo "Please re-download the app or install Python 3.10+ from python.org"
    osascript -e 'display dialog "Python environment is missing.\n\nPlease re-download the app from GitHub Releases." buttons {"OK"} default button 1 with icon stop'
    exit 1
fi

# Run the app with all arguments
exec "$VENV_PYTHON" main.py "$@"
LAUNCHER

chmod +x "${MACOS_DIR}/realtime-subtitle"

# ---- Step 5: Create Info.plist ----
echo "[5/6] Creating Info.plist..."
cat > "${CONTENTS}/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>RealtimeSubtitle</string>
    <key>CFBundleDisplayName</key>
    <string>Realtime Subtitle</string>
    <key>CFBundleIdentifier</key>
    <string>com.realtimesubtitle.app</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>realtime-subtitle</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>LSArchitecturePriority</key>
    <array>
        <string>arm64</string>
    </array>
    <key>NSMicrophoneUsageDescription</key>
    <string>Realtime Subtitle needs microphone access for real-time speech recognition and translation.</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>Realtime Subtitle uses Apple Events for keyboard shortcuts.</string>
    <key>NSSystemAdministrationUsageDescription</key>
    <string>Realtime Subtitle may need accessibility access for global shortcuts.</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# ---- Step 6: Create DMG ----
echo "[6/6] Creating DMG..."
rm -f "${DIST_DIR}/${DMG_NAME}"

hdiutil create -volname "${APP_NAME}" \
    -srcfolder "${BUILD_DIR}" \
    -ov -format UDZO \
    "${DIST_DIR}/${DMG_NAME}" 2>&1

# ---- Verify ----
if [ -f "${DIST_DIR}/${DMG_NAME}" ]; then
    SIZE=$(du -h "${DIST_DIR}/${DMG_NAME}" | cut -f1)
    echo ""
    echo "============================================"
    echo "  DMG created successfully!"
    echo "  ${DIST_DIR}/${DMG_NAME}"
    echo "  Size: ${SIZE}"
    echo "============================================"
    echo ""
    echo "Bundle layout:"
    find "${APP_BUNDLE}" -maxdepth 4 -not -path '*/venv/lib/*' -not -path '*/__pycache__/*' | head -50
    echo ""
    echo "To distribute:"
    echo "  1. Upload ${DMG_NAME} to GitHub Releases"
    echo "  2. Users download → open DMG → drag to Applications"
    echo "  3. First launch: right-click → Open (unsigned app)"
    echo ""
    echo "To test locally before distribution:"
    echo "  open ${APP_BUNDLE}"
    echo ""
    echo "⚠️  NOT code-signed. Users must right-click → Open."
else
    echo "ERROR: DMG creation failed!"
    exit 1
fi
