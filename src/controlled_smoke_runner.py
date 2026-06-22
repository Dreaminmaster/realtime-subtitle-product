#!/usr/bin/env python3
"""Run the v2.4 architecture controlled smoke test.

    python3 src/controlled_smoke_runner.py [--output report.json]
"""
import sys, json, os, time
from pathlib import Path
from dataclasses import asdict
from src.controlled_smoke import run_controlled_smoke


def main():
    result = run_controlled_smoke()
    report = {
        "type": "v2.4_architecture_smoke",
        "timestamp": time.time(),
        "result": asdict(result),
    }
    output_path = sys.argv[1] if len(sys.argv) > 1 else None
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"✅ Smoke report written to {output_path}")

    if result.ok:
        print(f"✅ PASS — session={result.session_id[:8]}, segments={result.segment_count}")
        sys.exit(0)
    else:
        print(f"❌ FAIL — {len(result.errors)} step(s) failed:")
        for e in result.errors:
            print(f"   - {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
