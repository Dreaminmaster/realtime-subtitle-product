#!/bin/bash
# =============================================================================
# DMG Packaging Script for Realtime Subtitle
#
# Packs portable Python + source code into .app, NO pre-built venv.
# Venv is created on the USER's machine on first launch, so it never
# contains GitHub runner paths.
#
# Usage:  bash build_dmg.sh <version> [arm64|x86_64]
# =============================================================================
set -e

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: bash build_dmg.sh <version> [arm64|x86_64]"
    exit 2
fi
VERSION_INPUT="$1"
VERSION="${VERSION_INPUT#v}"
if ! [[ "${VERSION}" =~ ^[0-9]+(\.[0-9]+){2}(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$ ]]; then
    echo "ERROR: version must be semantic, for example 2.4.0 or 2.4.0-rc1"
    exit 2
fi
HOST_ARCH=$(uname -m)
ARCH_INPUT="${2:-${HOST_ARCH}}"
case "${ARCH_INPUT}" in
    arm64|aarch64) ARCH="arm64" ;;
    x86_64|amd64) ARCH="x86_64" ;;
    *)
        echo "ERROR: architecture must be arm64 or x86_64"
        exit 2
        ;;
esac

BUNDLE_VERSION="${VERSION%%-*}"
APP_NAME="RealtimeSubtitle"
DMG_NAME="${APP_NAME}-${VERSION}-macos-${ARCH}.dmg"
VOLUME_NAME="${APP_NAME}-${ARCH}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build/${ARCH}"
APP_BUNDLE="${BUILD_DIR}/${APP_NAME}.app"
CONTENTS="${APP_BUNDLE}/Contents"
MACOS_DIR="${CONTENTS}/MacOS"
RESOURCES="${CONTENTS}/Resources"
PYTHON_DIR="${RESOURCES}/python"
PYTHON_BIN="${PYTHON_DIR}/bin/python3"
DIST_DIR="${SCRIPT_DIR}/dist"

# Portable Python source
PYTHON_STANDALONE_TAG="20260602"
if [ "${ARCH}" = "arm64" ]; then
    PYTHON_PLATFORM="aarch64-apple-darwin"
else
    PYTHON_PLATFORM="x86_64-apple-darwin"
fi
PYTHON_FILENAME="cpython-3.12.13%2B20260602-${PYTHON_PLATFORM}-install_only.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_STANDALONE_TAG}/${PYTHON_FILENAME}"
PYTHON_CACHE="${SCRIPT_DIR}/.python_cache/cpython-3.12-${ARCH}.tar.gz"

run_arch() {
    if [ "${HOST_ARCH}" = "arm64" ] && [ "${ARCH}" = "x86_64" ]; then
        /usr/bin/arch -x86_64 "$@"
    elif [ "${HOST_ARCH}" = "x86_64" ] && [ "${ARCH}" = "arm64" ]; then
        echo "ERROR: arm64 builds require an arm64 host (use GitHub's macos-15 runner)" >&2
        return 1
    else
        "$@"
    fi
}

echo "============================================"
echo "  Building ${APP_NAME} v${VERSION} for ${ARCH}"
echo "============================================"
echo ""

# ---- Clean ----
rm -rf "${BUILD_DIR}"
# Detach any leftover mounts from previous runs
hdiutil detach "/Volumes/${VOLUME_NAME}" 2>/dev/null || true
mkdir -p "${MACOS_DIR}" "${RESOURCES}" "${DIST_DIR}"

# ---- Step 1: Download & unpack portable Python ----
echo "[1/8] Setting up portable Python..."
if [ ! -f "${PYTHON_CACHE}" ]; then
    mkdir -p "${SCRIPT_DIR}/.python_cache"
    echo "  Downloading portable Python 3.12 (${ARCH})..."
    curl -L --retry 3 -o "${PYTHON_CACHE}" "${PYTHON_URL}" 2>&1
fi

mkdir -p "${PYTHON_DIR}"
tar xzf "${PYTHON_CACHE}" -C "${PYTHON_DIR}" --strip-components=1 2>&1
PYTHON_VERSION=$(run_arch "${PYTHON_BIN}" --version 2>&1)
echo "  Python: ${PYTHON_VERSION}"
PYTHON_FILE_INFO=$(file "${PYTHON_BIN}")
if [[ "${ARCH}" = "arm64" && "${PYTHON_FILE_INFO}" != *"arm64"* ]] \
   || [[ "${ARCH}" = "x86_64" && "${PYTHON_FILE_INFO}" != *"x86_64"* ]]; then
    echo "  ERROR: bundled Python architecture mismatch: ${PYTHON_FILE_INFO}"
    exit 1
fi

# ---- Step 1.5: Install PyQt6 into portable Python (bootstrap dependency) ----
echo "[1.5/8] Installing bootstrap PyQt6 into portable Python..."
run_arch "${PYTHON_BIN}" -m pip install --no-cache-dir --quiet PyQt6 2>&1 || {
    echo "  ERROR: failed to install PyQt6 into bundled Python"
    exit 1
}
run_arch "${PYTHON_BIN}" -c "import PyQt6" || { echo "  ERROR: PyQt6 import failed"; exit 1; }
echo "  ✅ PyQt6 OK in bundled Python"

# ---- Step 2: Copy project source ----
echo "[2/8] Copying source files…"
rsync -av --exclude='.git' \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='build' \
      --exclude='dist' \
      --exclude='transcripts' \
      --exclude='.DS_Store' \
      --exclude='*.dmg' \
      --exclude='.python_cache' \
      --exclude='.venv' \
      --exclude='.pytest_cache' \
      --exclude='.ruff_cache' \
      --exclude='.coverage' \
      --exclude='.gitignore' \
      --exclude='.github' \
      --exclude='tests' \
      --exclude='tools' \
      --exclude='docs' \
      --exclude='benchmarks' \
      --exclude='demo' \
      --exclude='build_dmg.sh' \
      --exclude='install_mac.sh' \
      --exclude='install_windows.bat' \
      --exclude='start_mac.sh' \
      --exclude='start_windows.bat' \
      --exclude='pytest.ini' \
      --exclude='test_funasr.py' \
      --exclude='FUNASR_GUIDE.md' \
      --exclude='FUNASR_IMPLEMENTATION_SUMMARY.md' \
      --exclude='SPEAKER_RECOGNITION.md' \
      --exclude='requirements_spec.md' \
      --exclude='runtime/test_reports' \
      --exclude='native/mac-translation' \
      --exclude='assets/icon/*-chroma.png' \
      --exclude='python' \
      --exclude='venv' \
      --exclude='wheelhouse' \
      "${SCRIPT_DIR}/" "${RESOURCES}/" 2>/dev/null

# Always stamp local and CI builds from the version argument.  This avoids
# stale source-tree constants and keeps the bundle identity reproducible.
VERSION_NO_V="${VERSION}"
BUILD_COMMIT=$(git -C "${SCRIPT_DIR}" rev-parse --short=10 HEAD 2>/dev/null || echo "unknown")
if ! git -C "${SCRIPT_DIR}" diff --quiet --ignore-submodules -- 2>/dev/null \
   || ! git -C "${SCRIPT_DIR}" diff --cached --quiet --ignore-submodules -- 2>/dev/null \
   || [ -n "$(git -C "${SCRIPT_DIR}" ls-files --others --exclude-standard 2>/dev/null)" ]; then
    BUILD_COMMIT="${BUILD_COMMIT}-dirty"
fi
BUILD_TIME=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
cat > "${RESOURCES}/version.py" <<EOF
BUILD_VERSION = "${VERSION_NO_V}"
BUILD_COMMIT = "${BUILD_COMMIT}"
BUILD_TIME = "${BUILD_TIME}"
BUILD_ARCH = "${ARCH}"
EOF
echo "  Build identity: v${VERSION_NO_V} (${BUILD_COMMIT}, ${ARCH})"
echo "  Done."

# Build a tiny native ScreenCaptureKit bridge so system audio works without
# BlackHole or any separately installed virtual sound device.
echo "[2.2/8] Building native system-audio helper…"
SYSTEM_AUDIO_BIN="${RESOURCES}/bin/system-audio-capture"
mkdir -p "$(dirname "${SYSTEM_AUDIO_BIN}")"
xcrun swiftc -O -parse-as-library \
    -target "${ARCH}-apple-macos13.0" \
    "${SCRIPT_DIR}/native/SystemAudioCapture.swift" \
    -framework ScreenCaptureKit \
    -framework AVFoundation \
    -framework CoreMedia \
    -o "${SYSTEM_AUDIO_BIN}"
chmod +x "${SYSTEM_AUDIO_BIN}"
SYSTEM_AUDIO_INFO=$(file "${SYSTEM_AUDIO_BIN}")
if [[ "${ARCH}" = "arm64" && "${SYSTEM_AUDIO_INFO}" != *"arm64"* ]] \
   || [[ "${ARCH}" = "x86_64" && "${SYSTEM_AUDIO_INFO}" != *"x86_64"* ]]; then
    echo "  ERROR: system-audio helper architecture mismatch: ${SYSTEM_AUDIO_INFO}"
    exit 1
fi
echo "  ✅ native system audio (${ARCH})"

# Apple's Translation framework is exposed through a tiny Swift command-line
# bridge.  The Python process stays portable while the actual translation and
# downloaded language assets remain entirely inside macOS.
echo "[2.3/8] Building Apple Translation helper…"
TRANSLATION_BIN="${RESOURCES}/bin/mac-translation"
xcrun swiftc -O -parse-as-library \
    -target "${ARCH}-apple-macos15.0" \
    "${SCRIPT_DIR}/native/MacTranslation.swift" \
    -framework Translation \
    -framework NaturalLanguage \
    -o "${TRANSLATION_BIN}"
chmod +x "${TRANSLATION_BIN}"
TRANSLATION_INFO=$(file "${TRANSLATION_BIN}")
if [[ "${ARCH}" = "arm64" && "${TRANSLATION_INFO}" != *"arm64"* ]] \
   || [[ "${ARCH}" = "x86_64" && "${TRANSLATION_INFO}" != *"x86_64"* ]]; then
    echo "  ERROR: Apple Translation helper architecture mismatch: ${TRANSLATION_INFO}"
    exit 1
fi
echo "  ✅ Apple Translation (${ARCH})"

# ---- Step 2.5: Build wheelhouse (offline dependency bundle) ----
echo "[2.5/8] Building wheelhouse…"
WHEELHOUSE_DIR="${RESOURCES}/wheelhouse"
rm -rf "${WHEELHOUSE_DIR}"
mkdir -p "${WHEELHOUSE_DIR}"

# Download all wheels for requirements-core.txt (binary only, no source dists)
echo "  Downloading wheels..."
run_arch "${PYTHON_BIN}" -m pip download \
    --dest "${WHEELHOUSE_DIR}" \
    --only-binary=:all: \
    -r "${RESOURCES}/requirements-core.txt" 2>&1 | tail -3

WHL_COUNT=$(find "${WHEELHOUSE_DIR}" -name '*.whl' | wc -l | tr -d ' ')
echo "  Downloaded ${WHL_COUNT} wheels"

if [ "${WHL_COUNT}" -lt 8 ]; then
    echo "  ❌ Too few wheels (${WHL_COUNT}), expected ≥8 — wheelhouse incomplete"
    exit 1
fi

# Verify wheelhouse: clean venv → offline install → import check
echo "  Verifying wheelhouse with clean venv..."
TMP_VENV=$(mktemp -d)
run_arch "${PYTHON_BIN}" -m venv "${TMP_VENV}" 2>&1 || {
    echo "  ❌ Failed to create test venv"; exit 1
}

TMP_PY="${TMP_VENV}/bin/python3"
run_arch "${TMP_PY}" -m pip install \
    --no-index \
    --find-links "${WHEELHOUSE_DIR}" \
    --disable-pip-version-check \
    --no-input \
    -r "${RESOURCES}/requirements-core.txt" 2>&1 | tail -3

INSTALL_EXIT=$?
if [ $INSTALL_EXIT -ne 0 ]; then
    echo "  ❌ Offline install from wheelhouse FAILED"
    rm -rf "${TMP_VENV}"
    exit 1
fi

# Verify critical imports
IMPORT_CHECK=$(run_arch "${TMP_PY}" -c "
for m in ['PyQt6','numpy','sounddevice','httpx','openai','faster_whisper','sentencepiece']:
    __import__(m)
    print(f'  ✅ {m}')
" 2>&1)
IMPORT_EXIT=$?

rm -rf "${TMP_VENV}"

if [ $IMPORT_EXIT -ne 0 ]; then
    echo "  ❌ Import verification FAILED"
    echo "${IMPORT_CHECK}"
    exit 1
fi
echo "${IMPORT_CHECK}"
echo "  ✅ wheelhouse verified (${WHL_COUNT} wheels, offline install OK)"

# ---- Step 2.7: Bundle default model ----
echo "[2.7/8] Bundling default model (tiny)..."
BUNDLED_MODEL="${RESOURCES}/models/whisper/tiny"
rm -rf "${BUNDLED_MODEL}"
mkdir -p "${BUNDLED_MODEL}"

# Ensure huggingface_hub is available in portable Python for model download
run_arch "${PYTHON_BIN}" -c "import huggingface_hub" 2>/dev/null || {
    echo "  Installing huggingface-hub from wheelhouse..."
    run_arch "${PYTHON_BIN}" -m pip install --no-index \
        --find-links "${RESOURCES}/wheelhouse" \
        --disable-pip-version-check --no-input \
        huggingface-hub 2>&1 | tail -1
}

echo "  Downloading Systran/faster-whisper-tiny from Hugging Face..."
MODEL_DL=$(cd "${WHEELHOUSE_DIR}" && HOME="${TMP_HOME:-/tmp}" \
    run_arch "${PYTHON_BIN}" -c "
import os, shutil
os.environ['BUNDLED_MODEL'] = '${BUNDLED_MODEL}'
from huggingface_hub import snapshot_download
snap = snapshot_download('Systran/faster-whisper-tiny')
dest = os.environ['BUNDLED_MODEL']
count = 0
for f in os.listdir(snap):
    src = os.path.join(snap, f)
    if os.path.isfile(src):
        shutil.copy2(src, os.path.join(dest, f))
        count += 1
print(f'Copied {count} files')
" 2>&1)

echo "  ${MODEL_DL}"

# Verify key files
MISSING=false
for f in config.json model.bin tokenizer.json; do
    if [ ! -f "${BUNDLED_MODEL}/${f}" ]; then
        echo "  ❌ Missing: ${f}"; MISSING=true
    fi
done
if [ ! -f "${BUNDLED_MODEL}/vocabulary.json" ] && [ ! -f "${BUNDLED_MODEL}/vocab.json" ]; then
    echo "  ⚠ No vocabulary file found (may be optional)"
fi
if $MISSING; then
    echo "  ❌ Bundled model incomplete — BUILD FAILED"
    echo "  Files present:"
    ls -lah "${BUNDLED_MODEL}/"
    exit 1
fi
MODEL_SIZE=$(du -sh "${BUNDLED_MODEL}" 2>/dev/null | cut -f1)
echo "  ✅ Default model bundled (${MODEL_SIZE}, $(ls -1 "${BUNDLED_MODEL}" | wc -l | tr -d ' ') files)"
echo "  Model files:"
ls -lhS "${BUNDLED_MODEL}/"

# ---- Step 3: Create launcher (Plan A — user-local venv) ----
echo "[3/8] Creating launcher…"
cat > "${MACOS_DIR}/realtime-subtitle" << 'LAUNCHER'
#!/bin/bash
# =============================================================================
# Realtime Subtitle Launcher
# Bootstraps bundled Python → launcher.py → SetupController → Dashboard.
# Shell does NOT create venv or install deps — SetupController handles that.
# =============================================================================

set -e

while [ -h "$0" ]; do
    DIR="$(cd -P "$(dirname "$0")" && pwd)"
    SCRIPT="$(readlink "$0")"
    [[ "$SCRIPT" != /* ]] && SCRIPT="$DIR/$SCRIPT"
done
APP_DIR="$(cd -P "$(dirname "$0")/../.." && pwd)"
RESOURCES="${APP_DIR}/Contents/Resources"
BUNDLED_PYTHON="${RESOURCES}/python/bin/python3"
LOG_DIR="${HOME}/Library/Logs/RealtimeSubtitle"
LOG_FILE="${LOG_DIR}/launcher.log"

mkdir -p "$LOG_DIR"
exec 2>>"$LOG_FILE"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }
alert() { osascript -e "display dialog \"$1\" buttons {\"OK\"} default button 1 with icon stop"; }

log "=== Bootstrap started ==="

# Verify bundled Python
if [ ! -x "$BUNDLED_PYTHON" ]; then
    alert "App bundle is incomplete.\n\nBundled Python is missing.\nPlease re-download."
    exit 1
fi
log "Bundled Python: $("$BUNDLED_PYTHON" --version 2>&1)"

# Override portable Python's /install prefix
export PYTHONHOME="${RESOURCES}/python"
cd "$RESOURCES"

# Launch the setup/dashboard UI — all setup logic lives in Python, not here.
exec "$BUNDLED_PYTHON" launcher.py "$@"
LAUNCHER

chmod +x "${MACOS_DIR}/realtime-subtitle"

# ---- Step 4: App metadata and icon ----
echo "[4/8] Creating Info.plist…"
ICON_SOURCE="${SCRIPT_DIR}/assets/icon/AppIcon.icns"
if [ ! -f "${ICON_SOURCE}" ]; then
    echo "  ERROR: app icon is missing: ${ICON_SOURCE}"
    exit 1
fi
cp "${ICON_SOURCE}" "${RESOURCES}/AppIcon.icns"

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
    <string>${BUNDLE_VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${BUNDLE_VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>realtime-subtitle</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Realtime Subtitle needs microphone access for real-time speech recognition and translation.</string>
    <key>NSScreenCaptureUsageDescription</key>
    <string>Realtime Subtitle needs Screen &amp; System Audio Recording access when System Audio is selected as the input.</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# ---- Step 5: DMG ----
echo "[5/8] Building DMG…"
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

hdiutil create -volname "${VOLUME_NAME}" \
    -srcfolder "${TMP_DMG_DIR}" \
    -ov -format UDRW \
    -size ${DMG_SIZE_MB}m \
    "${DIST_DIR}/tmp-${ARCH}.dmg" 2>&1

DEVICE=$(hdiutil attach -readwrite -noverify -noautoopen "${DIST_DIR}/tmp-${ARCH}.dmg" 2>&1 | head -1 | awk '{print $1}')
if [ -n "$DEVICE" ]; then
    sleep 2
    osascript -e "
        tell application \"Finder\"
            tell disk \"${VOLUME_NAME}\"
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

hdiutil convert "${DIST_DIR}/tmp-${ARCH}.dmg" -format UDZO -o "${DIST_DIR}/${DMG_NAME}" 2>&1 || {
    echo "  convert failed, trying fallback..."
    hdiutil create -volname "${VOLUME_NAME}" \
        -srcfolder "${TMP_DMG_DIR}" \
        -ov -format UDZO \
        "${DIST_DIR}/${DMG_NAME}" 2>&1
}
rm -f "${DIST_DIR}/tmp-${ARCH}.dmg"

# ---- Step 6: Verify ----
echo ""
echo "[6/8] Verifying..."
FAIL=false

# DMG exists
if [ ! -f "${DIST_DIR}/${DMG_NAME}" ]; then
    echo "  ❌ DMG missing"; FAIL=true
fi

# Portable Python exists in bundle
if [ ! -x "${APP_BUNDLE}/Contents/Resources/python/bin/python3" ]; then
    echo "  ❌ portable python missing"; FAIL=true
else
    BUNDLE_PYTHON="${APP_BUNDLE}/Contents/Resources/python/bin/python3"
    if BUNDLE_PYTHON_VERSION=$(run_arch "${BUNDLE_PYTHON}" --version 2>&1); then
        echo "  ✅ portable python: ${BUNDLE_PYTHON_VERSION}"
    else
        echo "  ❌ portable python cannot start: ${BUNDLE_PYTHON_VERSION}"
        FAIL=true
    fi
fi

# App icon exists and is referenced by Info.plist.
if [ ! -f "${APP_BUNDLE}/Contents/Resources/AppIcon.icns" ]; then
    echo "  ❌ app icon missing"; FAIL=true
elif [ "$(plutil -extract CFBundleIconFile raw "${APP_BUNDLE}/Contents/Info.plist" 2>/dev/null)" != "AppIcon" ]; then
    echo "  ❌ app icon is not referenced by Info.plist"; FAIL=true
else
    echo "  ✅ app icon bundled"
fi

# Executable architecture must match the requested target.
BUNDLE_PYTHON_INFO=$(file "${APP_BUNDLE}/Contents/Resources/python/bin/python3")
if [[ "${ARCH}" = "arm64" && "${BUNDLE_PYTHON_INFO}" != *"arm64"* ]] \
   || [[ "${ARCH}" = "x86_64" && "${BUNDLE_PYTHON_INFO}" != *"x86_64"* ]]; then
    echo "  ❌ bundle architecture mismatch: ${BUNDLE_PYTHON_INFO}"; FAIL=true
else
    echo "  ✅ bundle architecture ${ARCH}"
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

# Native system-audio helper is bundled for the selected architecture.
SYSTEM_AUDIO_HELPER="${APP_BUNDLE}/Contents/Resources/bin/system-audio-capture"
if [ ! -x "${SYSTEM_AUDIO_HELPER}" ]; then
    echo "  ❌ native system-audio helper missing"; FAIL=true
else
    SYSTEM_AUDIO_VERIFY=$(file "${SYSTEM_AUDIO_HELPER}")
    if [[ "${ARCH}" = "arm64" && "${SYSTEM_AUDIO_VERIFY}" != *"arm64"* ]] \
       || [[ "${ARCH}" = "x86_64" && "${SYSTEM_AUDIO_VERIFY}" != *"x86_64"* ]]; then
        echo "  ❌ system-audio helper architecture mismatch: ${SYSTEM_AUDIO_VERIFY}"; FAIL=true
    else
        echo "  ✅ native system audio ${ARCH}"
    fi
fi

# Native Apple Translation helper is bundled for the selected architecture.
TRANSLATION_HELPER="${APP_BUNDLE}/Contents/Resources/bin/mac-translation"
if [ ! -x "${TRANSLATION_HELPER}" ]; then
    echo "  ❌ Apple Translation helper missing"; FAIL=true
else
    TRANSLATION_VERIFY=$(file "${TRANSLATION_HELPER}")
    if [[ "${ARCH}" = "arm64" && "${TRANSLATION_VERIFY}" != *"arm64"* ]] \
       || [[ "${ARCH}" = "x86_64" && "${TRANSLATION_VERIFY}" != *"x86_64"* ]]; then
        echo "  ❌ Apple Translation helper architecture mismatch: ${TRANSLATION_VERIFY}"; FAIL=true
    else
        echo "  ✅ Apple Translation ${ARCH}"
    fi
fi

# No builder paths in source code (excluding build scripts that contain this check)
if grep -RIl "/Users/runner" "${APP_BUNDLE}/Contents" \
     --exclude='build_dmg.sh' --exclude='build-dmg.yml' \
     --exclude='*.md' --exclude='*.pyc' \
     --exclude-dir='__pycache__' --exclude-dir='python' \
     2>/dev/null | grep -q .; then
    echo "❌ Builder path /Users/runner found in app code"
    grep -RIl "/Users/runner" "${APP_BUNDLE}/Contents" --exclude-dir='python' --exclude-dir='__pycache__' 2>/dev/null
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
    echo "  ✅ requirements.txt ($(wc -l < "${APP_BUNDLE}/Contents/Resources/requirements.txt") lines)"
fi

# Bundle metadata and stamped build identity
if ! plutil -lint "${APP_BUNDLE}/Contents/Info.plist" >/dev/null; then
    echo "  ❌ Info.plist is invalid"; FAIL=true
else
    ACTUAL_SHORT_VERSION=$(plutil -extract CFBundleShortVersionString raw "${APP_BUNDLE}/Contents/Info.plist")
    ACTUAL_BUNDLE_VERSION=$(plutil -extract CFBundleVersion raw "${APP_BUNDLE}/Contents/Info.plist")
    if [ "${ACTUAL_SHORT_VERSION}" != "${BUNDLE_VERSION}" ] || [ "${ACTUAL_BUNDLE_VERSION}" != "${BUNDLE_VERSION}" ]; then
        echo "  ❌ bundle version mismatch: short=${ACTUAL_SHORT_VERSION} build=${ACTUAL_BUNDLE_VERSION}"
        FAIL=true
    else
        echo "  ✅ bundle metadata version ${BUNDLE_VERSION}"
    fi
fi

if ! grep -q "BUILD_VERSION = \"${VERSION_NO_V}\"" "${APP_BUNDLE}/Contents/Resources/version.py"; then
    echo "  ❌ stamped build identity missing"; FAIL=true
else
    echo "  ✅ stamped build identity v${VERSION_NO_V}"
fi
if ! grep -q "BUILD_ARCH = \"${ARCH}\"" "${APP_BUNDLE}/Contents/Resources/version.py"; then
    echo "  ❌ stamped architecture missing"; FAIL=true
else
    echo "  ✅ stamped architecture ${ARCH}"
fi

for excluded in .venv tests tools docs benchmarks .github; do
    if [ -e "${APP_BUNDLE}/Contents/Resources/${excluded}" ]; then
        echo "  ❌ development path bundled: ${excluded}"; FAIL=true
    fi
done

# Wheelhouse exists and has wheels
if [ ! -d "${APP_BUNDLE}/Contents/Resources/wheelhouse" ]; then
    echo "  ❌ wheelhouse missing"; FAIL=true
else
    WHL_VERIFY=$(find "${APP_BUNDLE}/Contents/Resources/wheelhouse" -name '*.whl' | wc -l | tr -d ' ')
    if [ "${WHL_VERIFY}" -lt 8 ]; then
        echo "  ❌ wheelhouse incomplete (${WHL_VERIFY} wheels)"; FAIL=true
    else
        echo "  ✅ wheelhouse (${WHL_VERIFY} wheels)"
    fi
fi

# Bundled model exists
MODEL_DIR="${APP_BUNDLE}/Contents/Resources/models/whisper/tiny"
if [ ! -d "${MODEL_DIR}" ]; then
    echo "  ❌ bundled model missing"; FAIL=true
else
    BAD=false
    for f in config.json model.bin tokenizer.json; do
        [ -f "${MODEL_DIR}/${f}" ] || { echo "  ❌ Missing: ${f}"; BAD=true; }
    done
    if $BAD; then
        echo "  ❌ bundled model incomplete"; FAIL=true
    else
        MODEL_SIZE=$(du -sh "${MODEL_DIR}" 2>/dev/null | cut -f1)
        echo "  ✅ bundled model tiny (${MODEL_SIZE})"
        echo "  Files:"
        ls -lhS "${MODEL_DIR}/"
    fi
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
