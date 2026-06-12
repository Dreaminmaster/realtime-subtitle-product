#!/bin/bash
# =============================================================================
# DMG Packaging Script for Realtime Subtitle
#
# Packs portable Python + source code into .app, NO pre-built venv.
# Venv is created on the USER's machine on first launch, so it never
# contains GitHub runner paths.
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

# Portable Python source
PYTHON_STANDALONE_TAG="20260602"
PYTHON_FILENAME="cpython-3.12.13%2B20260602-aarch64-apple-darwin-install_only.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_STANDALONE_TAG}/${PYTHON_FILENAME}"

echo "============================================"
echo "  Building ${APP_NAME} v${VERSION}"
echo "============================================"
echo ""

# ---- Clean ----
rm -rf "${BUILD_DIR}" "${DIST_DIR}"
# Detach any leftover mounts from previous runs
hdiutil detach "/Volumes/${APP_NAME}" 2>/dev/null || true
mkdir -p "${MACOS_DIR}" "${RESOURCES}" "${DIST_DIR}"

# ---- Step 1: Download & unpack portable Python ----
echo "[1/6] Setting up portable Python..."
if [ ! -f "${SCRIPT_DIR}/.python_cache/cpython-3.12.tar.gz" ]; then
    mkdir -p "${SCRIPT_DIR}/.python_cache"
    echo "  Downloading portable Python 3.12..."
    curl -L --retry 3 -o "${SCRIPT_DIR}/.python_cache/cpython-3.12.tar.gz" "${PYTHON_URL}" 2>&1
fi

mkdir -p "${PYTHON_DIR}"
tar xzf "${SCRIPT_DIR}/.python_cache/cpython-3.12.tar.gz" -C "${PYTHON_DIR}" --strip-components=1 2>&1
echo "  Python: $(${PYTHON_BIN} --version 2>&1)"

# ---- Step 2: Copy project source ----
echo "[2/6] Copying source files..."
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
echo "  Done."

# ---- Step 3: Create launcher (Plan A — user-local venv) ----
echo "[3/6] Creating launcher..."
cat > "${MACOS_DIR}/realtime-subtitle" << 'LAUNCHER'
#!/bin/bash
# =============================================================================
# Realtime Subtitle Launcher
# Uses bundled portable Python. Creates venv in user's Application Support
# on first launch — NEVER pre-built on the build machine.
# =============================================================================

set -e

# Resolve app directory
while [ -h "$0" ]; do
    DIR="$(cd -P "$(dirname "$0")" && pwd)"
    SCRIPT="$(readlink "$0")"
    [[ "$SCRIPT" != /* ]] && SCRIPT="$DIR/$SCRIPT"
done
APP_DIR="$(cd -P "$(dirname "$0")/../.." && pwd)"
RESOURCES="${APP_DIR}/Contents/Resources"
BUNDLED_PYTHON="${RESOURCES}/python/bin/python3"

# User runtime directories
APP_SUPPORT="${HOME}/Library/Application Support/RealtimeSubtitle"
VENV_DIR="${APP_SUPPORT}/venv"
LOG_DIR="${HOME}/Library/Logs/RealtimeSubtitle"
LOG_FILE="${LOG_DIR}/launcher.log"

mkdir -p "$LOG_DIR"
exec 2>>"$LOG_FILE"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }
alert() { osascript -e "display dialog \"$1\" buttons {\"OK\"} default button 1 with icon stop"; }

log "=== Launcher started ==="
log "APP_DIR: $APP_DIR"
log "BUNDLED_PYTHON: $BUNDLED_PYTHON"

# Check bundled Python
if [ ! -x "$BUNDLED_PYTHON" ]; then
    log "ERROR: Bundled Python not found at $BUNDLED_PYTHON"
    alert "App bundle is incomplete.\n\nBundled Python is missing.\nPlease re-download from GitHub Releases."
    exit 1
fi
log "Bundled Python: $($BUNDLED_PYTHON --version 2>&1)"

# ---- First-launch or repair: create/verify venv in user directory ----
VENV_PYTHON="${VENV_DIR}/bin/python3"
SETUP_MARKER="${APP_SUPPORT}/.setup_complete"

if [ ! -x "$VENV_PYTHON" ] || [ ! -f "$SETUP_MARKER" ]; then
    # Venv exists but setup was incomplete (e.g. pip failed previously)
    if [ -d "$VENV_DIR" ]; then
        log "WARNING: Broken/incomplete venv detected, removing..."
        rm -rf "$VENV_DIR"
    fi
    rm -f "$SETUP_MARKER"
    log "=== First launch setup ==="
    echo "============================================"
    echo "  Realtime Subtitle — First Launch Setup"
    echo "  Log: $LOG_FILE"
    echo "============================================"
    echo ""
    
    mkdir -p "$APP_SUPPORT"
    
    echo "→ Creating Python environment..."
    log "Creating venv at $VENV_DIR"
    "$BUNDLED_PYTHON" -m venv --copies "$VENV_DIR" 2>&1 | tee -a "$LOG_FILE"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log "ERROR: venv creation failed"
        rm -rf "$VENV_DIR"
        alert "Failed to create Python environment.\n\nCheck log:\n$LOG_FILE"
        exit 1
    fi
    echo "  ✓ venv created"
    
    echo "→ Installing dependencies (this may take a few minutes)..."
    echo "→ DO NOT close this window."
    log "Upgrading pip..."
    "$VENV_PYTHON" -m pip install --no-cache-dir --quiet --upgrade pip >> "$LOG_FILE" 2>&1 || true
    
    REQ_FILE="${RESOURCES}/requirements-core.txt"
    SETUP_READY=false
    if [ -f "$REQ_FILE" ]; then
        log "Installing from requirements-core.txt"
        "$VENV_PYTHON" -m pip install --no-cache-dir -r "$REQ_FILE" >> "$LOG_FILE" 2>&1
        PIP_EXIT=$?
        
        if [ $PIP_EXIT -ne 0 ]; then
            # Retry once for transient network errors
            log "WARNING: pip install failed (exit $PIP_EXIT), retrying once..."
            "$VENV_PYTHON" -m pip install --no-cache-dir -r "$REQ_FILE" 2>&1 | tee -a "$LOG_FILE"
            PIP_EXIT=$?
        fi

        if [ $PIP_EXIT -eq 0 ]; then
            # Verify core imports actually work
            log "Verifying core imports..."
            if "$VENV_PYTHON" -c "import PyQt6, numpy, sounddevice, httpx, openai, faster_whisper" 2>&1 >> "$LOG_FILE"; then
                SETUP_READY=true
                log "Core imports verified"
            else
                log "ERROR: core imports verification failed"
            fi
        else
            log "ERROR: pip install failed (exit $PIP_EXIT)"
        fi

        if [ "$SETUP_READY" = true ]; then
            echo "  ✓ Dependencies installed"
            touch "${APP_SUPPORT}/.setup_complete"
        else
            echo "  ✗ Setup failed"
            echo ""
            log "ERROR: Setup incomplete. Removing broken venv."
            rm -rf "$VENV_DIR"
            rm -f "${APP_SUPPORT}/.setup_complete"
            alert "Dependency installation failed.\n\nThis may be a network issue.\n\nPlease check your internet connection and try again.\n\nLog: $LOG_FILE"
            exit 1
        fi
    else
        log "ERROR: requirements-core.txt not found in app bundle"
        alert "App bundle is incomplete.\n\nrequirements-core.txt is missing.\nPlease re-download from GitHub Releases."
        exit 1
    fi
    
    echo ""
    echo "============================================"
    echo "  Setup complete! Starting app..."
    echo "============================================"
    echo ""
    log "=== Setup complete ==="
fi

# Final pre-launch check: PyQt6 must be importable
if ! "$VENV_PYTHON" -c "import PyQt6" 2>/dev/null; then
    log "ERROR: PyQt6 not importable — setup may be incomplete"
    alert "PyQt6 is not installed.\n\nPlease run Repair Environment from Diagnostics,\nor delete:\n  $APP_SUPPORT\nand re-launch."
    exit 1
fi

log "Launching: $VENV_PYTHON main.py"
cd "$RESOURCES"

# Override portable Python's built-in /install prefix with the actual bundle path
export PYTHONHOME="${RESOURCES}/python"
exec "$VENV_PYTHON" main.py "$@"
LAUNCHER

chmod +x "${MACOS_DIR}/realtime-subtitle"

# ---- Step 4: Info.plist ----
echo "[4/6] Creating Info.plist..."
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

# ---- Step 5: DMG ----
echo "[5/6] Building DMG..."
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
DMG_SIZE_MB=$(( (APP_SIZE_KB + 50000) / 1024 + 200 ))

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
    hdiutil detach "${DEVICE}" -force 2>/dev/null || true
    sleep 1
fi

# Remove old DMG first
rm -f "${DIST_DIR}/${DMG_NAME}"

hdiutil convert "${DIST_DIR}/tmp.dmg" -format UDZO -o "${DIST_DIR}/${DMG_NAME}" 2>&1 || {
    echo "  convert failed, trying fallback..."
    hdiutil create -volname "${APP_NAME}" \
        -srcfolder "${TMP_DMG_DIR}" \
        -ov -format UDZO \
        "${DIST_DIR}/${DMG_NAME}" 2>&1
}
rm -f "${DIST_DIR}/tmp.dmg"

# ---- Step 6: Verify ----
echo ""
echo "[6/6] Verifying..."
FAIL=false

# DMG exists
if [ ! -f "${DIST_DIR}/${DMG_NAME}" ]; then
    echo "  ❌ DMG missing"; FAIL=true
fi

# Portable Python exists in bundle
if [ ! -x "${APP_BUNDLE}/Contents/Resources/python/bin/python3" ]; then
    echo "  ❌ portable python missing"; FAIL=true
else
    echo "  ✅ portable python: $(${APP_BUNDLE}/Contents/Resources/python/bin/python3 --version 2>&1)"
fi

# NO pre-built venv in bundle (that would carry builder paths!)
if [ -d "${APP_BUNDLE}/Contents/Resources/venv" ]; then
    echo "  ❌ pre-built venv found — REMOVE IT (would break on user machine)"
    FAIL=true
else
    echo "  ✅ no pre-built venv"
fi

# Launcher exists
if [ ! -f "${APP_BUNDLE}/Contents/MacOS/realtime-subtitle" ]; then
    echo "  ❌ launcher missing"; FAIL=true
else
    echo "  ✅ launcher present"
fi

# No builder paths in source code (excluding build scripts that contain this check)
if grep -R "/Users/runner" "${APP_BUNDLE}/Contents" --exclude='build_dmg.sh' --exclude='build-dmg.yml' --exclude='final-validation-report.md' --exclude='final-stabilization-audit.md' 2>/dev/null; then
    echo "  ❌ builder path /Users/runner found in bundle"
    FAIL=true
else
    echo "  ✅ no builder paths in bundle"
fi

# /install is expected in portable Python's _sysconfigdata (python-build-standalone artifact).
# Launcher overrides it via PYTHONHOME at runtime.
echo "  ℹ️  /install in sysconfig is expected (overridden by launcher)"

# requirements.txt in bundle
if [ ! -f "${APP_BUNDLE}/Contents/Resources/requirements.txt" ]; then
    echo "  ❌ requirements.txt missing"; FAIL=true
else
    echo "  ✅ requirements.txt ($(wc -l < ${APP_BUNDLE}/Contents/Resources/requirements.txt) lines)"
fi

if [ "$FAIL" = true ]; then
    echo ""
    echo "  ❌ VERIFICATION FAILED"
    exit 1
fi

SIZE=$(du -h "${DIST_DIR}/${DMG_NAME}" | cut -f1)
echo ""
echo "=============================="
echo "  ✅ DMG READY"
echo "  ${DIST_DIR}/${DMG_NAME}  (${SIZE})"
echo "=============================="
echo ""
echo "  Bundle contents: portable Python + source code only"
echo "  Venv created on user machine at first launch"
