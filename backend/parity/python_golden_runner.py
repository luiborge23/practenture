#!/usr/bin/env python3
"""Execute backend/simulation_engine.py for the shared cross-language fixture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Runner lives in backend/parity; expose backend modules without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import PlayerDecision, SessionConfiguration, TeamConfig  # noqa: E402
from simulation_engine import process_round  # noqa: E402


def normalize(result, state):
    demand = result.demand
    return {
        "round": result.round,
        "revenue": result.revenue,
        "costs": result.costs,
        "profit": result.profit,
        "marketShare": result.marketShare,
        "sqRating": result.sqRating,
        "cash": result.cash,
        "inventory": int(result.inventory),
        "equity": result.equity,
        "debt": result.debt,
        "sharesOutstanding": int(result.sharesOutstanding),
        "reputation": state["reputation"],
        "imageRating": state["imageRating"],
        "creditRating": {
            "a_plus": "A+", "a": "A", "a_minus": "A-", "b_plus": "B+", "b": "B",
            "b_minus": "B-", "c_plus": "C+", "c": "C", "c_minus": "C-",
        }.get(state["creditRating"], state["creditRating"]),
        "awarenessScore": result.awarenessScore,
        "eps": state["eps"],
        "roe": state["roe"],
        "stockPrice": state["stockPrice"],
        "epsScore": result.epsScore,
        "roeScore": result.roeScore,
        "stockPriceScore": result.stockPriceScore,
        "imageScore": result.imageScore,
        "creditScore": result.creditScore,
        "totalScore": result.totalScore,
        "productionCost": result.productionCost,
        "marketingCost": result.marketingCost,
        "demand": {key: int(value) for key, value in demand.items()},
    }


def main(fixture_path: str, output_path: str) -> None:
    fixture = json.loads(Path(fixture_path).read_text())
    output = {"cases": {}}
    for case in fixture["cases"]:
        config = SessionConfiguration(**case["config"])
        teams = [TeamConfig(teamName=t["name"]) for t in case["teams"]]
        decisions = {name: PlayerDecision(**decision) for name, decision in case["decisions"].items()}
        states = {
            t["name"]: {
                "cash": t["cash"], "inventory": t["inventory"], "reputation": t["reputation"],
                "cumulativeTQM": t["cumulativeTQM"], "equity": t["equity"], "debt": t["debt"],
                "sharesOutstanding": t["sharesOutstanding"], "sqRating": t["sqRating"],
                "imageRating": t["imageRating"], "creditRating": t["creditRating"],
                "totalScore": t["cumulativeInvestorScore"],
            }
            for t in case["teams"]
        }
        results, updated = process_round(config, teams, decisions, case["round"], states)
        # Add internal values needed for complete field parity but omitted by the backend DTO.
        # They are recomputed by the production engine and retained in its returned state.
        case_result = {}
        for result in results:
            state = updated[result.teamId]
            case_result[result.teamId] = normalize(result, state)
        output["cases"][case["name"]] = case_result
    Path(output_path).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python_golden_runner.py FIXTURE OUTPUT")
    main(sys.argv[1], sys.argv[2])
