#!/usr/bin/env python3
"""Compile production Swift engine, run both engines, and enforce golden parity."""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = HERE / ".build"
FIXTURE = HERE / "golden_cases.json"
_fixture_contract = json.loads(FIXTURE.read_text())
REL_TOL = float(_fixture_contract["tolerance"]["relative"])
ABS_TOL = float(_fixture_contract["tolerance"]["absolute"])


def run() -> tuple[list[dict], dict]:
    BUILD.mkdir(exist_ok=True)
    swift_bin = BUILD / "swift-golden-runner"
    swift_output = BUILD / "swift-output.json"
    python_output = BUILD / "python-output.json"
    subprocess.run([
        "swiftc",
        str(ROOT / "BizSimAI/Models/SimulationModels.swift"),
        str(ROOT / "BizSimAI/Engine/SimulationSnapshot.swift"),
        str(ROOT / "BizSimAI/Engine/SimulationEngine.swift"),
        str(HERE / "SwiftGoldenRunner.swift"), "-o", str(swift_bin),
    ], check=True, cwd=ROOT)
    subprocess.run([str(swift_bin), str(FIXTURE), str(swift_output)], check=True, cwd=ROOT)
    subprocess.run([
        sys.executable, str(HERE / "python_golden_runner.py"),
        str(FIXTURE), str(python_output),
    ], check=True, cwd=ROOT)
    swift = json.loads(swift_output.read_text())
    python = json.loads(python_output.read_text())
    mismatches: list[dict] = []
    stats = {"compared": 0, "passed": 0, "failed": 0, "maxRelativeError": 0.0}

    def compare(left, right, path="root"):
        if isinstance(left, dict) and isinstance(right, dict):
            if set(left) != set(right):
                mismatches.append({"path": path, "swiftKeys": sorted(left), "pythonKeys": sorted(right), "reason": "key mismatch"})
                stats["failed"] += 1
            for key in sorted(set(left) & set(right)):
                compare(left[key], right[key], f"{path}.{key}")
            return
        stats["compared"] += 1
        # Semantically integral state is exact even if a JSON encoder emits 20 vs 20.0.
        leaf = path.rsplit(".", 1)[-1]
        exact_integer_fields = {
            "round", "inventory", "sharesOutstanding", "wholesale", "internet",
            "amazon", "privateLabel", "totalSold",
        }
        if isinstance(left, (str, bool)) or isinstance(right, (str, bool)):
            ok = type(left) is type(right) and left == right
            relative = None
        elif leaf in exact_integer_fields:
            ok = isinstance(left, (int, float)) and isinstance(right, (int, float)) and left == right
            relative = None
        elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
            absolute = abs(float(left) - float(right))
            denominator = max(abs(float(left)), abs(float(right)))
            relative = absolute / denominator if denominator else 0.0
            stats["maxRelativeError"] = max(stats["maxRelativeError"], relative)
            ok = absolute <= ABS_TOL or relative <= REL_TOL
        else:
            relative = None
            ok = type(left) is type(right) and left == right
        if ok:
            stats["passed"] += 1
        else:
            stats["failed"] += 1
            mismatches.append({"path": path, "swift": left, "python": right, "relativeError": relative})

    compare(swift, python)
    return mismatches, stats


def main() -> int:
    mismatches, stats = run()
    report = {
        "status": "PASS" if not mismatches else "FAIL",
        "relativeTolerance": REL_TOL,
        "absoluteTolerance": ABS_TOL,
        "statistics": stats,
        "mismatches": mismatches,
    }
    report_path = BUILD / "parity-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({**report, "report": str(report_path)}, indent=2))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
