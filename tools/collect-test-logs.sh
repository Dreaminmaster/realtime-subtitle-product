#!/bin/bash
# Realtime Subtitle — Log Collector
# Run: bash collect-test-logs.sh [label]
# Zip: cd ~/Desktop && zip -r test-logs-YYYYMMDD-HHMMSS.zip ~/Library/Logs/RealtimeSubtitle/

LABEL="${1:-manual}"
DEST="$HOME/Desktop/test-logs-$(date +%Y%m%d-%H%M%S)-${LABEL}"
mkdir -p "$DEST"

# Copy app logs
if [ -d "$HOME/Library/Logs/RealtimeSubtitle" ]; then
    cp -r "$HOME/Library/Logs/RealtimeSubtitle" "$DEST/"
    echo "Collected: $DEST/RealtimeSubtitle/"
else
    echo "No logs at ~/Library/Logs/RealtimeSubtitle"
fi

# Copy system diagnostic
echo "=== System Info ===" > "$DEST/system-info.txt"
sw_vers >> "$DEST/system-info.txt" 2>/dev/null
echo "" >> "$DEST/system-info.txt"
python3 --version >> "$DEST/system-info.txt" 2>/dev/null
echo "" >> "$DEST/system-info.txt"
sysctl -n machdep.cpu.brand_string >> "$DEST/system-info.txt" 2>/dev/null

# App structure snapshot
if [ -d "/Applications/RealtimeSubtitle.app" ]; then
    echo "" >> "$DEST/system-info.txt"
    echo "=== App Tree ===" >> "$DEST/system-info.txt"
    find /Applications/RealtimeSubtitle.app -maxdepth 4 -not -path '*/venv/lib/*' -not -path '*/venv/lib64/*' | head -100 >> "$DEST/system-info.txt"
fi

# Process snapshot
echo "" >> "$DEST/system-info.txt"
echo "=== Process List ===" >> "$DEST/system-info.txt"
ps aux | grep -i "realtimesubtitle\|main.py\|python.*venv" | grep -v grep >> "$DEST/system-info.txt"

echo ""
echo "Logs collected to: $DEST"
echo "Zip for sharing: cd ~/Desktop && zip -r $(basename $DEST).zip $(basename $DEST)"
