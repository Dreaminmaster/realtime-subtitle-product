#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="${SCRIPT_DIR}/assets/icon/realtime-subtitle-icon.png"
OUTPUT="${SCRIPT_DIR}/assets/icon/AppIcon.icns"

if [ ! -f "${SOURCE}" ]; then
    echo "Missing icon source: ${SOURCE}" >&2
    exit 1
fi

PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

"${PYTHON_BIN}" -c "
from PIL import Image
source = Image.open('${SOURCE}').convert('RGBA')
master = source.resize((1024, 1024), Image.Resampling.LANCZOS)
master.save(
    '${OUTPUT}',
    format='ICNS',
    sizes=[(16,16), (32,32), (64,64), (128,128),
           (256,256), (512,512), (1024,1024)],
)
"
echo "Created ${OUTPUT}"
