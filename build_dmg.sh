#!/bin/bash
# =============================================================================
# DMG Packaging Script for Realtime Subtitle
#
# Creates an .app bundle that sets up its own Python environment on first launch.
# The venv is NOT built during DMG creation (to avoid machine-specific binary issues).
# Instead, the launcher auto-creates the venv using the user's system Python.
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
DIST_DIR="${SCRIPT_DIR}/dist"

echo "============================================"
echo "  Building ${APP_NAME} v${VERSION}"
echo "============================================"
echo ""

# ---- Clean ----
rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${MACOS_DIR}" "${RESOURCES}" "${DIST_DIR}"

# ---- Step 1: Copy project files into Resources ----
echo "[1/6] Copying project files..."
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
echo "  Files copied to: ${RESOURCES}"

# ---- Step 2: Create launcher script ----
echo "[2/6] Creating launcher script..."
cat > "${MACOS_DIR}/realtime-subtitle" << 'LAUNCHER'
#!/bin/bash
# =============================================================================
# Realtime Subtitle Launcher
# First-launch: auto-creates a Python venv using SYSTEM Python and installs deps.
# Subsequent launches: uses the existing venv.
# =============================================================================

# Resolve real script location
while [ -h "$0" ]; do
    DIR="$(cd -P "$(dirname "$0")" && pwd)"
    SCRIPT="$(readlink "$0")"
    [[ "$SCRIPT" != /* ]] && SCRIPT="$DIR/$SCRIPT"
done
APP_DIR="$(cd -P "$(dirname "$0")/../.." && pwd)"
RESOURCES="${APP_DIR}/Contents/Resources"
VENV_DIR="${RESOURCES}/venv"
VENV_PYTHON="${VENV_DIR}/bin/python3"

cd "$RESOURCES"

# ---- Check venv health ----
venv_ok=false
if [ -f "$VENV_PYTHON" ] && [ -x "$VENV_PYTHON" ]; then
    if "$VENV_PYTHON" -c '' 2>/dev/null; then
        venv_ok=true
    fi
fi

# ---- First-launch / repair: create venv ----
if [ "$venv_ok" = false ]; then
    echo "============================================"
    echo "  Realtime Subtitle — First Launch Setup"
    echo "============================================"
    echo ""
    
    # Find system Python
    SYSTEM_PYTHON=""
    for candidate in /usr/local/bin/python3 /opt/homebrew/bin/python3 /usr/bin/python3; do
        if [ -x "$candidate" ] && "$candidate" -c '' 2>/dev/null; then
            PY_VER=$("$candidate" -c 'import sys; print(sys.version_info[:2])' 2>/dev/null)
            PY_MAJOR=$(echo "$PY_VER" | cut -d',' -f1 | tr -d ' ()')
            PY_MINOR=$(echo "$PY_VER" | cut -d',' -f2 | tr -d ' ')
            if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
                SYSTEM_PYTHON="$candidate"
                break
            fi
        fi
    done
    
    if [ -z "$SYSTEM_PYTHON" ]; then
        osascript -e 'display dialog "Python 3.10+ is required.\n\nPlease install Python from python.org/downloads\n\nAfter installing, re-open this app." buttons {"OK"} default button 1 with icon stop'
        exit 1
    fi
    
    echo "System Python: $SYSTEM_PYTHON ($($SYSTEM_PYTHON --version))"
    echo ""
    
    # Create venv
    echo "Creating Python environment..."
    rm -rf "$VENV_DIR"
    "$SYSTEM_PYTHON" -m venv --copies "$VENV_DIR" 2>/dev/null || \
    "$SYSTEM_PYTHON" -m venv "$VENV_DIR" 2>/dev/null || {
        osascript -e 'display dialog "Failed to create Python environment.\n\nPlease ensure Python 3.10+ is installed from python.org" buttons {"OK"} default button 1 with icon stop'
        exit 1
    }
    
    VENV_PYTHON="${VENV_DIR}/bin/python3"
    
    # Upgrade pip
    echo "Upgrading pip..."
    "$VENV_PYTHON" -m pip install --no-cache-dir --quiet --upgrade pip 2>/dev/null || true
    
    # Install dependencies
    if [ -f "${RESOURCES}/requirements.txt" ]; then
        echo "Installing dependencies..."
        "$VENV_PYTHON" -m pip install --no-cache-dir --quiet -r requirements.txt 2>&1 || {
            # Retry with verbose output for diagnostics
            echo "Retrying with verbose output..."
            "$VENV_PYTHON" -m pip install --no-cache-dir -r requirements.txt 2>&1
        }
    fi
    
    echo ""
    echo "============================================"
    echo "  Setup complete! Starting app..."
    echo "============================================"
    echo ""
fi

# ---- Launch ----
exec "$VENV_PYTHON" main.py "$@"
LAUNCHER

chmod +x "${MACOS_DIR}/realtime-subtitle"

# ---- Step 3: Create Info.plist ----
echo "[3/6] Creating Info.plist..."
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

# ---- Step 4: Create DMG background ----
echo "[4/6] Creating DMG background..."
python3 -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (600, 400), color=(40, 40, 52))
draw = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 24)
except:
    font = ImageFont.load_default()
draw.text((190, 180), '→ Drag to Applications', fill=(205, 214, 244), font=font)
img.save('${RESOURCES}/dmg_background.png', 'PNG')
print('  Background OK')
" 2>&1 || echo "  Background skipped (PIL not available)"

# ---- Step 5: Create DMG layout ----
echo "[5/6] Creating DMG volume layout..."
TMP_DMG_DIR="${BUILD_DIR}/dmg_layout"
rm -rf "${TMP_DMG_DIR}"
mkdir -p "${TMP_DMG_DIR}"

cp -R "${APP_BUNDLE}" "${TMP_DMG_DIR}/"

# Remove .deps_installed if it exists (force fresh setup per user)
rm -f "${TMP_DMG_DIR}/${APP_NAME}.app/Contents/Resources/.deps_installed" 2>/dev/null || true

# Remove background from inside bundle
rm -f "${TMP_DMG_DIR}/${APP_NAME}.app/Contents/Resources/dmg_background.png" 2>/dev/null || true

# Applications symlink
ln -s /Applications "${TMP_DMG_DIR}/Applications"

# Background image for DMG
mkdir -p "${TMP_DMG_DIR}/.background"
cp "${RESOURCES}/dmg_background.png" "${TMP_DMG_DIR}/.background/background.png" 2>/dev/null || true

# Size estimate
APP_SIZE_KB=$(du -sk "${TMP_DMG_DIR}" | cut -f1)
DMG_SIZE_MB=$(( (APP_SIZE_KB + 50000) / 1024 + 200 ))
echo "  App bundle size: $((APP_SIZE_KB / 1024)) MB, DMG size: ${DMG_SIZE_MB} MB"

# ---- Step 6: Build DMG ----
echo "[6/6] Creating DMG..."
rm -f "${DIST_DIR}/${DMG_NAME}"

hdiutil create -volname "${APP_NAME}" \
    -srcfolder "${TMP_DMG_DIR}" \
    -ov -format UDRW \
    -size ${DMG_SIZE_MB}m \
    "${DIST_DIR}/tmp_${DMG_NAME}" 2>&1

DEVICE=$(hdiutil attach -readwrite -noverify -noautoopen "${DIST_DIR}/tmp_${DMG_NAME}" 2>&1 | head -1 | awk '{print $1}')

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

hdiutil convert "${DIST_DIR}/tmp_${DMG_NAME}" \
    -format UDZO \
    -o "${DIST_DIR}/${DMG_NAME}" 2>&1

rm -f "${DIST_DIR}/tmp_${DMG_NAME}"

# ---- Step 7: Verify ----
echo ""
echo "[7/7] Verifying..."
SELF_CHECK_FAILED=false

# Check DMG file exists
if [ ! -f "${DIST_DIR}/${DMG_NAME}" ]; then
    echo "  ❌ DMG file not found"
    exit 1
fi

SIZE=$(du -h "${DIST_DIR}/${DMG_NAME}" | cut -f1)
echo "  ✅ DMG created: ${DIST_DIR}/${DMG_NAME} (${SIZE})"

# Check launcher exists in bundle
if [ ! -f "${APP_BUNDLE}/Contents/MacOS/realtime-subtitle" ]; then
    echo "  ❌ Launcher missing"
    SELF_CHECK_FAILED=true
else
    echo "  ✅ Launcher present"
fi

# Check requirements.txt in bundle
if [ ! -f "${APP_BUNDLE}/Contents/Resources/requirements.txt" ]; then
    echo "  ❌ requirements.txt missing from bundle"
    SELF_CHECK_FAILED=true
else
    echo "  ✅ requirements.txt present"
fi

# Check main.py in bundle
if [ ! -f "${APP_BUNDLE}/Contents/Resources/main.py" ]; then
    echo "  ❌ main.py missing from bundle"
    SELF_CHECK_FAILED=true
else
    echo "  ✅ main.py present"
fi

if [ "$SELF_CHECK_FAILED" = true ]; then
    echo ""
    echo "  ❌ Verification FAILED — see above"
    exit 1
fi

echo ""
echo "============================================"
echo "  ✅ DMG created and verified!"
echo "  ${DIST_DIR}/${DMG_NAME}"
echo "  Size: ${SIZE}"
echo "============================================"
echo ""
echo "  First-launch behavior:"
echo "    User opens .app → launcher detects no venv"
echo "    → auto-creates venv from system Python"
echo "    → pip install -r requirements.txt"
echo "    → launches main.py"
echo ""
echo "  Download: https://github.com/Dreaminmaster/realtime-subtitle-product/releases"
