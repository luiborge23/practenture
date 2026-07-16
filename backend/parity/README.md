# Swift ↔ Python Golden Parity Harness

This directory runs a shared deterministic fixture through the production Swift
`SimulationEngine` and Python `simulation_engine.py`, then recursively compares
normalized complete-round metrics.

## Formula ownership

Network games are **backend-authoritative**: `NetworkService.processRound` posts to
`/api/sessions/{code}/process_round` and the iOS client decodes the returned results.
The app also has a deliberate local/offline path (`GameController` and
`SimulationEngine`) that computes the same round locally. Therefore this is a parity
gate for an existing offline implementation, not a new client-side reimplementation.
The Swift adapter invokes production `SimulationEngine.processRoundPure`; it contains
no simulation formulas.

```bash
backend/.venv/bin/python backend/parity/verify_golden_parity.py
```

The verifier:

1. Compiles the checked-in Swift engine/model sources with a minimal session adapter.
2. Runs both engines against `golden_cases.json` with the same fixed 64-bit seed.
3. Requires exact equality for categorical and integral state/demand values.
4. Loads its tolerances from the machine-readable fixture (`relative <= 0.001`, or
   `absolute <= 1e-9` at/near zero).
5. Writes raw outputs and `parity-report.json` under `.build/` and exits nonzero on
   any mismatch.

`customerSatisfaction` and `rejectionRate` are intentionally excluded because
the Python production result/state API does not return enough information to
observe them without reimplementing backend internals in the runner.

The checked-in cases explicitly tag representative competition, deterministic noise,
zero-production/zero-debt denominator guards, negative financial state, fractional
rounding, saturation/caps, boundary values, and private-label allocation.
