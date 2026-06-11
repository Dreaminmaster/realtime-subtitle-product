#!/bin/bash
# =============================================================================
# DMG Packaging Script for Realtime Subtitle
#
# Creates a self-contained .app bundle with a portable Python runtime.
# The Python 3.12 framework is downloaded from python.org and bundled inside
# the .app — no system Python, Homebrew, or FlyEnv needed.
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
PYTHON_DIR="${RESOURCES}/python"
PYTHON_BIN="${PYTHON_DIR}/bin/python3"
DIST_DIR="${SCRIPT_DIR}/dist"

# Use Python 3.12 — stable, well-tested, available as portable build
PYTHON_VERSION="3.12.12"
PYTHON_TAR="python-${PYTHON_VERSION}-macos11.tar.gz"
PYTHON_URL="https://github.com/indygreg/python-build-standalone/releases/download/20250825/cpython-${PYTHON_VERSION}+20250825-aarch64-apple-darwin-install_only.tar.gz"

echo "============================================"
echo "  Building ${APP_NAME} v${VERSION}"
echo "============================================"
echo ""

# ---- Clean ----
rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${MACOS_DIR}" "${RESOURCES}" "${DIST_DIR}"

# ---- Step 1: Download portable Python ----
echo "[1/7] Setting up portable Python..."
if [ ! -f "${SCRIPT_DIR}/.python_cache/${PYTHON_TAR}" ]; then
    mkdir -p "${SCRIPT_DIR}/.python_cache"
    echo "  Downloading Python ${PYTHON_VERSION} (portable build)..."
    curl -L --retry 3 -o "${SCRIPT_DIR}/.python_cache/${PYTHON_TAR}" "${PYTHON_URL}" 2>&1
fi

mkdir -p "${PYTHON_DIR}"
tar xzf "${SCRIPT_DIR}/.python_cache/${PYTHON_TAR}" -C "${PYTHON_DIR}" --strip-components=1 2>&1
echo "  Python: $(${PYTHON_BIN} --version 2>&1)"

# ---- Step 2: Create venv from portable Python ----
echo "[2/7] Creating venv..."
"${PYTHON_BIN}" -m venv --copies "${RESOURCES}/venv" 2>&1
VENV_PYTHON="${RESOURCES}/venv/bin/python3"

# ---- Step 3: Install dependencies ----
echo "[3/7] Installing Python dependencies..."
"${VENV_PYTHON}" -m pip install --no-cache-dir --quiet --upgrade pip 2>/dev/null || true

echo "  From requirements.txt:"
cat "${SCRIPT_DIR}/requirements.txt"

"${VENV_PYTHON}" -m pip install --no-cache-dir -r "${SCRIPT_DIR}/requirements.txt" 2>&1

# Verify key imports
echo "  Verifying imports..."
"${VENV_PYTHON}" -c "import PyQt6, numpy, sounddevice; print('  ✓ PyQt6, numpy, sounddevice OK')" 2>&1

# ---- Step 4: Copy project files ----
echo "[4/7] Copying project files..."
rsync -av --exclude='.git' \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='build' \
      --exclude='dist' \
      --exclude='transcripts' \
      --exclude='.DS_Store' \
      --exclude='*.dmg' \
      --exclude='.python_cache' \
      --exclude='python' \
      --exclude='venv' \
      "${SCRIPT_DIR}/" "${RESOURCES}/" 2>/dev/null
echo "  Files copied."

# ---- Step 5: Create launcher ----
echo "[5/7] Creating launcher..."
cat > "${MACOS_DIR}/realtime-subtitle" << 'LAUNCHER'
#!/bin/bash
# Realtime Subtitle Launcher — uses bundled Python venv only.

while [ -h "$0" ]; do
    DIR="$(cd -P "$(dirname "$0")" && pwd)"
    SCRIPT="$(readlink "$0")"
    [[ "$SCRIPT" != /* ]] && SCRIPT="$DIR/$SCRIPT"
done
APP_DIR="$(cd -P "$(dirname "$0")/../.." && pwd)"
RESOURCES="${APP_DIR}/Contents/Resources"
VENV_PYTHON="${RESOURCES}/venv/bin/python3"

if [ ! -f "$VENV_PYTHON" ]; then
    osascript -e 'display dialog "App bundle is incomplete.\n\nBundled Python environment is missing.\nPlease re-download from GitHub Releases." buttons {"OK"} default button 1 with icon stop'
    exit 1
fi

cd "$RESOURCES"
exec "$VENV_PYTHON" main.py "$@"
LAUNCHER

chmod +x "${MACOS_DIR}/realtime-subtitle"

# ---- Step 6: Info.plist ----
echo "[6/7] Creating Info.plist..."
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
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Realtime Subtitle needs microphone access for real-time speech recognition and translation.</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# ---- Step 7: DMG ----
echo "[7/7] Building DMG..."
TMP_DMG_DIR="${BUILD_DIR}/dmg_layout"
rm -rf "${TMP_DMG_DIR}"
mkdir -p "${TMP_DMG_DIR}"

cp -R "${APP_BUNDLE}" "${TMP_DMG_DIR}/"
ln -s /Applications "${TMP_DMG_DIR}/Applications"

# Background
mkdir -p "${TMP_DMG_DIR}/.background"
python3 -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (600, 400), (40, 40, 52))
d = ImageDraw.Draw(img)
try: f = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 24)
except: f = ImageFont.load_default()
d.text((180, 180), '→ Drag to Applications', fill=(205, 214, 244), font=f)
img.save('${TMP_DMG_DIR}/.background/background.png', 'PNG')
" 2>/dev/null || echo "  (no PIL, skipping bg)"

APP_SIZE_KB=$(du -sk "${TMP_DMG_DIR}" | cut -f1)
DMG_SIZE_MB=$(( (APP_SIZE_KB + 100000) / 1024 + 200 ))

hdiutil create -volname "${APP_NAME}" \
    -srcfolder "${TMP_DMG_DIR}" \
    -ov -format UDRW \
    -size ${DMG_SIZE_MB}m \
    "${DIST_DIR}/tmp.dmg" 2>&1

DEVICE=$(hdiutil attach -readwrite -noverify -noautoopen "${DIST_DIR}/tmp.dmg" 2>&1 | head -1 | awk '{print $1}')
if [ -n "$DEVICE" ]; then
    sleep 2
    osascript -e "
        tell application \"Finder\"
            tell disk \"${APP_NAME}\"
                open
                set current view of container window to icon view
                set toolbar visible of container window to false
                set statusbar visible of container window to false
                set bounds of container window to {100, 100, 700, 500}
                set viewOptions to the icon view options of container window
                set arrangement of viewOptions to not arranged
                set icon size of viewOptions to 72
                set background picture of viewOptions to file \".background:background.png\"
                set position of item \"${APP_NAME}.app\" of container window to {120, 150}
                set position of item \"Applications\" of container window to {420, 150}
                update without registering applications
                close
            end tell
        end tell
    " 2>/dev/null || true
    sleep 2
    hdiutil detach "${DEVICE}" -force 2>/dev/null
fi

hdiutil convert "${DIST_DIR}/tmp.dmg" -format UDZO -o "${DIST_DIR}/${DMG_NAME}" 2>&1
rm -f "${DIST_DIR}/tmp.dmg"

# ---- Verify ----
echo ""
echo "=============================="
echo "  VERIFICATION"
echo "=============================="
FAIL=false

if [ ! -f "${DIST_DIR}/${DMG_NAME}" ]; then
    echo "  ❌ DMG missing"
    FAIL=true
fi

if [ ! -f "${APP_BUNDLE}/Contents/Resources/venv/bin/python3" ]; then
    echo "  ❌ venv/bin/python3 missing"
    FAIL=true
else
    echo "  ✅ venv/bin/python3 exists"
    ${VENV_PYTHON} --version 2>&1 && echo "  ✅ Python works" || FAIL=true
    ${VENV_PYTHON} -c "import PyQt6, numpy, sounddevice; print('  ✅ PyQt6, numpy, sounddevice OK')" 2>&1 || FAIL=true
fi

SIZE=$(du -h "${DIST_DIR}/${DMG_NAME}" 2>/dev/null | cut -f1)
echo "  DMG size: ${SIZE}"

if [ "$FAIL" = true ]; then
    echo ""
    echo "  ❌ VERIFICATION FAILED"
    exit 1
fi

echo ""
echo "=============================="
echo "  ✅ DMG READY"
echo "  ${DIST_DIR}/${DMG_NAME}"
echo "=============================="
