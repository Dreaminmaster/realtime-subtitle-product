#!/bin/bash
set -euo pipefail

APP_BUNDLE="${1:?app bundle required}"
IDENTITY="${2:--}"
ENTITLEMENTS="${3:-$(cd "$(dirname "$0")/.." && pwd)/packaging/macos/RealtimeSubtitle.entitlements}"
SPARKLE="${APP_BUNDLE}/Contents/Frameworks/Sparkle.framework"

SIGN_ARGS=(--force --sign "${IDENTITY}")
if [[ "${IDENTITY}" != "-" ]]; then
    SIGN_ARGS+=(--timestamp --options runtime)
fi

sign_file() {
    local target="$1"
    [[ -e "${target}" ]] || return 0
    codesign "${SIGN_ARGS[@]}" "$target"
}

# Sign every bundled Mach-O dependency before its container.  Portable Python,
# PyQt, CTranslate2 and audio extensions all live in Resources rather than a
# conventional Frameworks directory.
while IFS= read -r -d '' candidate; do
    if file -b "${candidate}" | grep -q 'Mach-O'; then
        sign_file "${candidate}"
    fi
done < <(find "${APP_BUNDLE}/Contents/Resources" -type f -print0)

# The signed launcher execs the bundled Python binary.  Hardened-runtime
# permissions therefore belong on Python itself as well as the outer app;
# otherwise CTranslate2/PyQt extensions from the user-local environment are
# rejected after notarization.
if [[ "${IDENTITY}" != "-" ]]; then
    codesign "${SIGN_ARGS[@]}" --entitlements "${ENTITLEMENTS}" \
        "${APP_BUNDLE}/Contents/Resources/python/bin/python3.12"
fi

# Sparkle's XPC services and updater app must be signed inside-out using the
# same identity as the host application (Sparkle 2 sandbox/signing guidance).
sign_file "${SPARKLE}/Versions/B/XPCServices/Downloader.xpc"
sign_file "${SPARKLE}/Versions/B/XPCServices/Installer.xpc"
sign_file "${SPARKLE}/Versions/B/Updater.app"
sign_file "${SPARKLE}/Versions/B/Autoupdate"
sign_file "${SPARKLE}/Versions/B/Sparkle"
sign_file "${SPARKLE}"
sign_file "${APP_BUNDLE}/Contents/Frameworks/libRealtimeSubtitleUpdater.dylib"
sign_file "${APP_BUNDLE}/Contents/MacOS/realtime-subtitle"

APP_ARGS=("${SIGN_ARGS[@]}")
if [[ "${IDENTITY}" != "-" ]]; then
    APP_ARGS+=(--entitlements "${ENTITLEMENTS}")
fi
codesign "${APP_ARGS[@]}" "${APP_BUNDLE}"
codesign --verify --deep --strict --verbose=2 "${APP_BUNDLE}"
