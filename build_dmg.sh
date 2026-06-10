#!/bin/bash
# =============================================================================
# DMG Packaging Script for Realtime Subtitle
# 
# Creates a distributable .dmg file for macOS.
# Usage: bash build_dmg.sh [version]
# =============================================================================

set -e

VERSION="${1:-1.0.0}"
APP_NAME="RealtimeSubtitle"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${PROJECT_DIR}/build"
APP_BUNDLE="${BUILD_DIR}/${APP_NAME}.app"
DMG_PATH="${PROJECT_DIR}/dist/${DMG_NAME}"

echo "============================================"
echo "  Building ${APP_NAME} v${VERSION}"
echo "============================================"

# Step 1: Create app bundle structure
echo ""
echo "[1/6] Creating .app bundle..."

rm -rf "${APP_BUNDLE}"
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"
mkdir -p "${PROJECT_DIR}/dist"

# Step 2: Create the launcher script
echo "[2/6] Creating launcher script..."

cat > "${APP_BUNDLE}/Contents/MacOS/launch.sh" << 'LAUNCHER'
#!/bin/bash
# Realtime Subtitle Launcher
# Sets up environment and launches the app

APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
RESOURCES="${APP_DIR}/Contents/Resources"

# Ensure we use the right Python
if [ -f "${RESOURCES}/venv/bin/python3" ]; then
    PYTHON="${RESOURCES}/venv/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "Error: Python 3 not found. Please install Python 3.10+ from python.org"
    osascript -e 'display dialog "Python 3 is required. Download from python.org" buttons {"OK"} default button 1 with icon stop'
    exit 1
fi

# Set up environment
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
export PYTHONPATH="${RESOURCES}:${APP_DIR}/Contents/python:$PYTHONPATH"

cd "${RESOURCES}"

# Check dependencies
if [ ! -f "${RESOURCES}/.deps_installed" ]; then
    echo "Installing dependencies..."
    "${PYTHON}" -m pip install --quiet -r requirements.txt 2>/dev/null || true
    touch "${RESOURCES}/.deps_installed"
fi

# Launch
exec "${PYTHON}" main.py "$@"
LAUNCHER

chmod +x "${APP_BUNDLE}/Contents/MacOS/launch.sh"

# Step 3: Create Info.plist
echo "[3/6] Creating Info.plist..."

cat > "${APP_BUNDLE}/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>Realtime Subtitle</string>
    <key>CFBundleIdentifier</key>
    <string>com.realtimesubtitle.app</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>launch.sh</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>LSArchitecturePriority</key>
    <array>
        <string>arm64</string>
    </array>
    <key>NSMicrophoneUsageDescription</key>
    <string>Realtime Subtitle needs microphone access for speech recognition.</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>Realtime Subtitle uses Apple Events for keyboard shortcuts.</string>
    <key>NSSystemAdministrationUsageDescription</key>
    <string>Realtime Subtitle may need accessibility access for global shortcuts.</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# Step 4: Copy project files to Resources
echo "[4/6] Copying project files..."

rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
      --exclude='build' --exclude='dist' --exclude='transcripts' \
      --exclude='.DS_Store' --exclude='*.dmg' \
      "${PROJECT_DIR}/" "${APP_BUNDLE}/Contents/Resources/" 2>/dev/null

# Step 5: Clean up and create DMG
echo "[5/6] Creating DMG..."

# Remove old DMG
rm -f "${DMG_PATH}"

# Create DMG
hdiutil create -volname "${APP_NAME}" \
    -srcfolder "${BUILD_DIR}" \
    -ov -format UDZO \
    "${DMG_PATH}" 2>&1

# Step 6: Verify
echo "[6/6] Verifying DMG..."

if [ -f "${DMG_PATH}" ]; then
    SIZE=$(du -h "${DMG_PATH}" | cut -f1)
    echo ""
    echo "============================================"
    echo "  ✅ DMG created successfully!"
    echo "  📦 ${DMG_PATH}"
    echo "  📏 Size: ${SIZE}"
    echo "============================================"
    echo ""
    echo "To distribute:"
    echo "  1. Upload ${DMG_NAME} to GitHub Releases or website"
    echo "  2. Users download and open the DMG"
    echo "  3. Drag RealtimeSubtitle.app to Applications"
    echo "  4. Right-click → Open (for unsigned app on first launch)"
    echo ""
    echo "⚠️  Note: This app is NOT code-signed."
    echo "    Users may need to right-click → Open the first time."
    echo "    For public distribution, consider Apple notarization."
else
    echo "❌ DMG creation failed!"
    exit 1
fi
