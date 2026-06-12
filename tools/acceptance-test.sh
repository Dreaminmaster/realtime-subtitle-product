#!/bin/bash
# Realtime Subtitle — Mac Acceptance Test Script
# v2.2.7-rc
# Run: bash acceptance-test.sh

APP="/Applications/RealtimeSubtitle.app"
LOG_DIR="$HOME/Library/Logs/RealtimeSubtitle"
REPORT="~/Desktop/acceptance-report-$(date +%Y%m%d-%H%M%S).txt"

echo "============================================"
echo " Realtime Subtitle — Acceptance Test v2.2.7"
echo " $(date)"
echo "============================================"
echo ""

echo "--- Build Identity ---"
echo "Tag: v2.2.7"
echo "Commit: 6d210b7 (after grep fix)"
echo ""

echo "--- 1. App Presence ---"
if [ -d "$APP" ]; then
    echo "  ✅ App installed: $APP"
    echo "  Package size: $(du -sh "$APP" 2>/dev/null | awk '{print $1}')"
else
    echo "  ❌ App NOT found at $APP"
fi

echo ""
echo "--- 2. Bundle Structure ---"
for check in \
    "Contents/MacOS/realtime-subtitle" \
    "Contents/Resources/python/bin/python3" \
    "Contents/Resources/requirements-core.txt" \
    "Contents/Resources/main.py" \
    "Contents/Info.plist"
do
    if [ -f "$APP/$check" ]; then
        echo "  ✅ $check"
    else
        echo "  ❌ MISSING: $check"
    fi
done

echo ""
echo "--- 3. Venv State ---"
VENV="$HOME/Library/Application Support/RealtimeSubtitle/venv"
if [ -d "$VENV" ]; then
    echo "  Venv exists: $VENV"
    echo "  Size: $(du -sh "$VENV" 2>/dev/null | awk '{print $1}')"
    if [ -f "$VENV/bin/python3" ]; then
        echo "  Python: $($VENV/bin/python3 --version 2>&1)"
        echo "  PyQt6: $($VENV/bin/python3 -c 'import PyQt6; print(PyQt6.__version__)' 2>&1)"
    fi
else
    echo "  Venv NOT yet created (first launch not performed)"
fi
echo "  Setup marker: $([ -f "$HOME/Library/Application Support/RealtimeSubtitle/.setup_complete" ] && echo 'exists' || echo 'missing')"

echo ""
echo "--- 4. Logs ---"
if [ -d "$LOG_DIR" ]; then
    echo "  Log dir: $LOG_DIR"
    echo "  Files: $(ls -la "$LOG_DIR" 2>/dev/null | wc -l)"
    for f in "$LOG_DIR"/*.log; do
        echo "    $(basename $f): $(wc -l < "$f" 2>/dev/null) lines"
    done
else
    echo "  Log dir not yet created"
fi

echo ""
echo "--- 5. Process Check ---"
PROCS=$(ps aux 2>/dev/null | grep -i "realtimesubtitle\|main.py.*overlay" | grep -v grep | wc -l)
if [ "$PROCS" -eq 0 ]; then
    echo "  ✅ No residual processes"
else
    echo "  ⚠️  $PROCS process(es) running:"
    ps aux | grep -i "realtimesubtitle\|main.py" | grep -v grep
fi

echo ""
echo "--- 6. App Log Last 20 Lines ---"
if [ -f "$LOG_DIR/app.log" ]; then
    tail -20 "$LOG_DIR/app.log"
fi

echo ""
echo "============================================"
echo " Acceptance test snapshot complete"
echo "============================================"
