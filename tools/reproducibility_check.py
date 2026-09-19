#!/usr/bin/env python3
"""Reproducibility verification for DevLens scan reports.

Runs a DevLens scan against a target directory twice in a row and
compares the resulting JSON reports (after stripping fields that are
inherently non-deterministic, such as scan duration and absolute
timestamps) to confirm that DevLens produces byte-for-byte identical
findings, scores, and ordering across repeated runs.

Usage:
    python tools/reproducibility_check.py [path_to_scan]

Exit codes:
    0 = reports match (reproducible)
    1 = reports differ (non-reproducible; a bug)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from devlens.scanner import ScanOptions, run_scan  # noqa: E402

# Fields that are expected to vary between runs (wall-clock timing) and
# are excluded from the reproducibility comparison on purpose.
VOLATILE_KEYS = {"scan_duration_seconds"}


def _strip_volatile(data):
    if isinstance(data, dict):
        return {k: _strip_volatile(v) for k, v in data.items() if k not in VOLATILE_KEYS}
    if isinstance(data, list):
        return [_strip_volatile(v) for v in data]
    return data


def run_once(path: str) -> dict:
    options = ScanOptions(path=path)
    result = run_scan(options)
    return _strip_volatile(result.to_dict())


def stable_hash(data: dict) -> str:
    encoded = json.dumps(data, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "examples/demo_project"

    print("=" * 60)
    print("DEV LENS REPRODUCIBILITY CHECK")
    print("=" * 60)
    print(f"\nTarget: {target}\n")

    print("Running scan #1...")
    first = run_once(target)
    print("Running scan #2...")
    second = run_once(target)

    hash1 = stable_hash(first)
    hash2 = stable_hash(second)

    print(f"\nScan #1 hash: {hash1}")
    print(f"Scan #2 hash: {hash2}")

    if hash1 == hash2:
        print("\nResult: PASS - reports are reproducible (identical after removing timing fields).")
        return 0

    print("\nResult: FAIL - reports differ between runs.")
    _print_diff_summary(first, second)
    return 1


def _print_diff_summary(a: dict, b: dict) -> None:
    a_findings = {f["id"] for f in a.get("findings", [])}
    b_findings = {f["id"] for f in b.get("findings", [])}
    only_a = a_findings - b_findings
    only_b = b_findings - a_findings
    if only_a:
        print(f"  Findings only in run #1: {sorted(only_a)}")
    if only_b:
        print(f"  Findings only in run #2: {sorted(only_b)}")
    if a.get("scores") != b.get("scores"):
        print(f"  Scores differ: {a.get('scores')} vs {b.get('scores')}")


if __name__ == "__main__":
    sys.exit(main())
