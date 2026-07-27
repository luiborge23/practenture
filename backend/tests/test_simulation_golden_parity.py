"""Executable contract for the production Swift/Python simulation parity gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
PARITY = BACKEND / "parity"
FIXTURE = PARITY / "golden_cases.json"


def test_golden_fixture_declares_required_edge_contract() -> None:
    fixture = json.loads(FIXTURE.read_text())

    assert fixture["schemaVersion"] == 1
    assert fixture["tolerance"] == {"relative": 0.001, "absolute": 1e-9}
    assert len(fixture["cases"]) >= 3

    coverage = {tag for case in fixture["cases"] for tag in case["covers"]}
    assert {
        "representative",
        "divide_by_zero",
        "negative",
        "rounding",
        "growth_cap",
        "capacity_cap",
        "seeded_noise",
    } <= coverage


def test_production_swift_and_python_engines_are_within_fixture_tolerance() -> None:
    completed = subprocess.run(
        [sys.executable, str(PARITY / "verify_golden_parity.py")],
        check=True,
        cwd=BACKEND.parent,
        text=True,
        capture_output=True,
    )
    report = json.loads(completed.stdout)

    assert report["status"] == "PASS"
    assert report["relativeTolerance"] == 0.001
    assert report["absoluteTolerance"] == 1e-9
    assert report["statistics"]["failed"] == 0
    assert report["statistics"]["compared"] >= 150
    assert report["statistics"]["maxRelativeError"] <= 0.001

    # Prove that the edge fixture exercised finite zero-denominator handling and
    # negative results, rather than merely tagging an unobserved input.
    python_output = json.loads((PARITY / ".build/python-output.json").read_text())
    edge = python_output["cases"]["zero_production_negative_cash_rounding"]["Edge Zero"]
    assert edge["demand"]["totalSold"] == 0
    assert edge["debt"] == 0
    assert edge["cash"] < 0
    # Equity = initial_equity (1.0) + profit (-1.01) = -0.01.
    # Both Swift and Python engines agree; the previous assertion expected
    # the pre-round initial equity, not the post-round result.
    assert edge["equity"] == -0.01
    assert edge["sharesOutstanding"] == 1
