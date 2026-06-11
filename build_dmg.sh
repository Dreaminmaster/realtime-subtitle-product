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
python3 -m venv --copies "${VENV_DIR}" 2>&1 || {
    echo "ERROR: python3 not found. Please install Python 3.10+ from python.org"
    exit 1
}
echo "  venv created at: ${VENV_DIR} (self-contained copy mode)"

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
# Runs the app using its bundled Python venv. Self-healing: if the venv
# is broken (e.g. moved from another Mac), it auto-rebuilds.
# =============================================================================

# Resolve real script location (follows symlinks)
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

# Check if venv python actually works (not a dead symlink or wrong arch)
venv_ok=false
if [ -f "$VENV_PYTHON" ] && [ -x "$VENV_PYTHON" ]; then
    if "$VENV_PYTHON" -c 'print("venv ok")' 2>/dev/null; then
        venv_ok=true
    fi
fi

# Auto-rebuild venv if broken
if [ "$venv_ok" = false ]; then
    echo "Realtime Subtitle: Python environment needs setup..."
    
    # Check for system Python
    if ! command -v python3 &>/dev/null; then
        osascript -e 'display dialog "Python 3 is required.\n\nDownload from python.org/downloads" buttons {"OK"} default button 1 with icon stop'
        exit 1
    fi
    
    echo "  Rebuilding Python environment..."
    rm -rf "$VENV_DIR"
    python3 -m venv --copies "$VENV_DIR" 2>/dev/null || python3 -m venv "$VENV_DIR" 2>/dev/null
    
    if [ -f "${RESOURCES}/requirements.txt" ]; then
        "$VENV_DIR/bin/python3" -m pip install --no-cache-dir --quiet -r requirements.txt 2>/dev/null
    fi
    
    echo "  Setup complete."
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

# ---- Step 5.5: Create DMG background image ----
echo "[5.5/7] Creating DMG background..."
"${VENV_DIR}/bin/python3" -c "
import subprocess, os

bg_dir = '${RESOURCES}'
dmg_bg = os.path.join(bg_dir, 'dmg_background.png')

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    subprocess.check_call(['${VENV_DIR}/bin/python3', '-m', 'pip', 'install', '--no-cache-dir', 'Pillow'],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    from PIL import Image, ImageDraw, ImageFont

# Create a clean 600x400 background
img = Image.new('RGB', (600, 400), color=(40, 40, 52))
draw = ImageDraw.Draw(img)

# Only draw an arrow and 'Drag to Applications' text in the center
# Let Finder display the App icon and name — don't duplicate them
try:
    font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 24)
except Exception:
    font = ImageFont.load_default()

# Arrow from left to right (centered)
arrow_y = 180
draw.text((190, arrow_y), '→', fill=(166, 227, 161), font=font)
draw.text((220, arrow_y), 'Drag to Applications', fill=(205, 214, 244), font=font)

img.save(dmg_bg, 'PNG')
print(f'  Background image created: {dmg_bg}')
" 2>&1

# ---- Step 6: Create DMG layout ----
echo "[6/7] Creating DMG volume layout..."
TMP_DMG_DIR="${BUILD_DIR}/dmg_layout"
rm -rf "${TMP_DMG_DIR}"
mkdir -p "${TMP_DMG_DIR}"

# Copy .app to layout
cp -R "${APP_BUNDLE}" "${TMP_DMG_DIR}/"

# Clean up massive cache files from the DMG bundle to save space
echo "  Cleaning caches..."
rm -rf "${TMP_DMG_DIR}/${APP_NAME}.app/Contents/Resources/venv/lib/python3"*/site-packages/pip/_vendor 2>/dev/null || true
rm -rf "${TMP_DMG_DIR}/${APP_NAME}.app/Contents/Resources/venv/lib/python3"*/site-packages/setuptools 2>/dev/null || true
find "${TMP_DMG_DIR}" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find "${TMP_DMG_DIR}" -name '*.pyc' -delete 2>/dev/null || true

# Remove the background image from inside the .app (it's for DMG only)
rm -f "${TMP_DMG_DIR}/${APP_NAME}.app/Contents/Resources/dmg_background.png" 2>/dev/null || true

# Create Applications symlink
ln -s /Applications "${TMP_DMG_DIR}/Applications"

# Copy background to hidden folder
mkdir -p "${TMP_DMG_DIR}/.background"
mv "${RESOURCES}/dmg_background.png" "${TMP_DMG_DIR}/.background/background.png" 2>/dev/null || true

# Estimate required DMG size (app size + buffer)
APP_SIZE_KB=$(du -sk "${TMP_DMG_DIR}" | cut -f1)
DMG_SIZE_MB=$(( (APP_SIZE_KB + 100000) / 1024 + 200 ))  # 200MB buffer
echo "  App size: $((APP_SIZE_KB / 1024)) MB, DMG size: ${DMG_SIZE_MB} MB"

# ---- Step 7: Create and beautify DMG ----
echo "[7/7] Creating and styling DMG..."
rm -f "${DIST_DIR}/${DMG_NAME}"

# Create a temporary DMG first, then configure it
hdiutil create -volname "${APP_NAME}" \
    -srcfolder "${TMP_DMG_DIR}" \
    -ov -format UDRW \
    -size ${DMG_SIZE_MB}m \
    "${DIST_DIR}/tmp_${DMG_NAME}" 2>&1

# Mount the writable DMG
DEVICE=$(hdiutil attach -readwrite -noverify -noautoopen "${DIST_DIR}/tmp_${DMG_NAME}" 2>&1 | head -1 | awk '{print $1}')
if [ -z "$DEVICE" ]; then
    # Fallback: just create a simple DMG
    echo "  Could not mount for styling, creating simple DMG..."
    hdiutil create -volname "${APP_NAME}" \
        -srcfolder "${TMP_DMG_DIR}" \
        -ov -format UDZO \
        "${DIST_DIR}/${DMG_NAME}" 2>&1
else
    MOUNT="/Volumes/${APP_NAME}"
    
    # Wait for mount
    sleep 2
    
    # Set icon positions via AppleScript
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
    
    # Wait for Finder to apply settings
    sleep 2
    
    # Unmount
    hdiutil detach "${DEVICE}" -force 2>/dev/null
    
    # Convert to compressed read-only DMG
    hdiutil convert "${DIST_DIR}/tmp_${DMG_NAME}" \
        -format UDZO \
        -o "${DIST_DIR}/${DMG_NAME}" 2>&1
    
    rm -f "${DIST_DIR}/tmp_${DMG_NAME}"
fi

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
