#!/usr/bin/env python3
"""Validate PRODUCT_GAP_AUDIT.md — parse, verify, count."""
import sys, re
from pathlib import Path

path = Path(__file__).parent.parent / "docs" / "PRODUCT_GAP_AUDIT.md"
text = path.read_text()
lines = text.splitlines()

VALID_STATES = {"COMPLETE_VERIFIED", "COMPLETE_UNVERIFIED", "PARTIAL", "MISSING", "KNOWN_LIMITATION"}
errors = 0
seen = set()
state_counts = {s: 0 for s in VALID_STATES}

for line in lines:
    line = line.strip()
    if not line.startswith("|"):
        continue
    cols = [c.strip() for c in line.split("|")]
    # Markdown tables have leading/trailing pipes: | col1 | col2 | ...
    # This gives cols = ['', 'col1', 'col2', ...] with first empty
    if len(cols) < 5:  # need at least: empty, num, item, status, rest...
        continue
    try:
        num = int(cols[1])  # column 1 = item number
    except ValueError:
        continue
    if num < 1 or num > 35:
        print(f"  ERROR: item number {num} out of range 1-35")
        errors += 1
        continue
    if num in seen:
        print(f"  ERROR: duplicate item #{num}")
        errors += 1
    seen.add(num)
    state = cols[3] if len(cols) > 3 else ""
    if state not in VALID_STATES:
        print(f"  ERROR: item #{num} invalid state '{state}'")
        errors += 1
    else:
        state_counts[state] += 1

missing = set(range(1, 36)) - seen
if missing:
    print(f"  ERROR: missing items: {sorted(missing)}")
    errors += 1

total = sum(state_counts.values())
if total != 35:
    print(f"  ERROR: total items {total}, expected 35")
    errors += 1

# Verify Summary matches
summary = {}
for line in lines:
    line = line.strip()
    m = re.match(r'- (\w+): (\d+)', line)
    if m:
        key = m.group(1)
        val = int(m.group(2))
        if key in VALID_STATES:
            summary[key] = val

summary_total = sum(summary.values())
if summary_total != 35:
    print(f"  ERROR: Summary total {summary_total}, expected 35")
    errors += 1
for s in VALID_STATES:
    if state_counts.get(s, 0) != summary.get(s, 0):
        print(f"  ERROR: {s}: table has {state_counts.get(s,0)}, Summary has {summary.get(s,0)}")
        errors += 1

if errors:
    print(f"\n=== FAILED: {errors} errors ===")
    sys.exit(1)
else:
    print(f"=== PASSED: 35 items verified ===")
    for s in sorted(VALID_STATES):
        print(f"  {s}: {state_counts.get(s, 0)}")
