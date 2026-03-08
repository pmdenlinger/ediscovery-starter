#!/usr/bin/env python3
"""
Quick DAT validator (very basic):
- Ensures consistent delimiter counts per row
- Prints line numbers with mismatches
"""
import sys, csv
DAT = sys.argv[1] if len(sys.argv) > 1 else "samples/sample-loadfile/sample.dat"
with open(DAT, encoding="utf-8", newline="") as f:
    reader = csv.reader(f, delimiter='|', quotechar='"')
    header = next(reader)
    fields = len(header)
    print(f"Header fields: {fields}")
    for i, row in enumerate(reader, start=2):
        if len(row) != fields:
            print(f"[WARN] Line {i}: {len(row)} fields (expected {fields})")
print("Done.")