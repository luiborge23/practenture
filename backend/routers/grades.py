"""Grade export endpoint — CSV download for professor."""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response

from auth import verify_professor
from database import db
from models import LeaderboardEntry

router = APIRouter(tags=["grades"])


def _verify_export_access(code: str, user: dict) -> None:
    """Restrict grade exports to the owning professor or platform owner."""
    if user.get("role") == "owner":
        return
    if db.get_session_professor_user_id(code) != user.get("sub"):
        raise HTTPException(status_code=403, detail="Not your session")


@router.get(
    "/api/sessions/{code}/export/grades",
    response_class=Response,
    responses={200: {"content": {"text/csv": {"schema": {"type": "string"}}}}},
)
async def export_grades(code: str, user=Depends(verify_professor)):
    """Export all round results as CSV for a session.
    
    Returns a CSV file with columns:
    Team, Round, Revenue, Costs, Profit, Market Share, S/Q Rating,
    Reputation, Cash, Equity, Debt, Shares Outstanding, EPS, ROE,
    Stock Price, Total Score
    """
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _verify_export_access(code, user)

    all_results = db.get_all_results(code)
    if not all_results:
        raise HTTPException(status_code=400, detail="No results available for export")

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Team", "Round", "Revenue", "Costs", "Profit",
        "Market Share", "S/Q Rating", "Reputation",
        "Cumulative Profit", "Cash", "Inventory", "Equity", "Debt",
        "Shares Outstanding", "EPS", "ROE", "Stock Price",
        "EPS Score", "ROE Score", "Stock Price Score",
        "Image Score", "Credit Score", "Total Score",
        "Unit Cost", "Production Cost", "Marketing Cost",
        "Wholesale Demand", "Internet Demand", "Amazon Demand", "Total Sold",
    ])

    # Data rows — one per team per round
    for round_num in sorted(all_results.keys()):
        for result in all_results[round_num]:
            demand = result.demand if hasattr(result, 'demand') and result.demand else {}
            writer.writerow([
                result.teamId,
                result.round,
                f"{result.revenue:,.2f}",
                f"{result.costs:,.2f}",
                f"{result.profit:,.2f}",
                f"{result.marketShare:.4f}",
                f"{result.sqRating:.2f}",
                f"{result.reputation:.2f}",
                f"{result.cumulativeProfit:,.2f}",
                f"{result.cash:,.2f}",
                f"{result.inventory:,.2f}",
                f"{result.equity:,.2f}",
                f"{result.debt:,.2f}",
                f"{result.sharesOutstanding:,.2f}",
                f"{result.eps:.4f}",
                f"{result.roe:.4f}",
                f"{result.stockPrice:.2f}",
                f"{result.epsScore:.2f}",
                f"{result.roeScore:.2f}",
                f"{result.stockPriceScore:.2f}",
                f"{result.imageScore:.2f}",
                f"{result.creditScore:.2f}",
                f"{result.totalScore:.2f}",
                f"{result.unitCost:.2f}",
                f"{result.productionCost:,.2f}",
                f"{result.marketingCost:,.2f}",
                f"{demand.get('wholesale', 0):,.2f}",
                f"{demand.get('internet', 0):,.2f}",
                f"{demand.get('amazon', 0):,.2f}",
                f"{demand.get('totalSold', 0):,.2f}",
            ])

    # Return as downloadable CSV
    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="practenture_{code}_grades.csv"'
        },
    )


@router.get(
    "/api/sessions/{code}/export/leaderboard",
    response_class=Response,
    responses={200: {"content": {"text/csv": {"schema": {"type": "string"}}}}},
)
async def export_leaderboard(code: str, user=Depends(verify_professor)):
    """Export final leaderboard as CSV."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _verify_export_access(code, user)

    all_results = db.get_all_results(code)
    if not all_results:
        raise HTTPException(status_code=400, detail="No results available")

    # Aggregate per-team scores
    team_data: dict = {}
    for round_num, results in sorted(all_results.items()):
        for r in results:
            if r.teamId not in team_data:
                team_data[r.teamId] = {
                    "teamName": r.teamId,
                    "revenue": 0, "costs": 0, "profit": 0,
                    "cumulativeProfit": 0, "cash": 0, "equity": 0,
                    "debt": 0, "stockPrice": 0, "eps": 0, "roe": 0,
                    "totalScore": 0, "sqRating": 0, "reputation": 0,
                    "marketShare": 0,
                }
            team_data[r.teamId]["revenue"] = r.revenue
            team_data[r.teamId]["costs"] = r.costs
            team_data[r.teamId]["profit"] = r.profit
            team_data[r.teamId]["cumulativeProfit"] = r.cumulativeProfit
            team_data[r.teamId]["cash"] = r.cash
            team_data[r.teamId]["equity"] = r.equity
            team_data[r.teamId]["debt"] = r.debt
            team_data[r.teamId]["stockPrice"] = r.stockPrice
            team_data[r.teamId]["eps"] = r.eps
            team_data[r.teamId]["roe"] = r.roe
            team_data[r.teamId]["totalScore"] = r.totalScore
            team_data[r.teamId]["sqRating"] = r.sqRating
            team_data[r.teamId]["reputation"] = r.reputation
            team_data[r.teamId]["marketShare"] = r.marketShare

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Rank", "Team", "Revenue", "Costs", "Profit",
        "Cumulative Profit", "Cash", "Equity", "Debt",
        "Stock Price", "EPS", "ROE", "Total Score",
        "S/Q Rating", "Reputation", "Market Share",
    ])

    # Sort by total score descending
    ranked = sorted(team_data.values(), key=lambda x: x["totalScore"], reverse=True)
    for rank, team in enumerate(ranked, 1):
        writer.writerow([
            rank,
            team["teamName"],
            f"{team['revenue']:,.2f}",
            f"{team['costs']:,.2f}",
            f"{team['profit']:,.2f}",
            f"{team['cumulativeProfit']:,.2f}",
            f"{team['cash']:,.2f}",
            f"{team['equity']:,.2f}",
            f"{team['debt']:,.2f}",
            f"{team['stockPrice']:.2f}",
            f"{team['eps']:.4f}",
            f"{team['roe']:.4f}",
            f"{team['totalScore']:.2f}",
            f"{team['sqRating']:.2f}",
            f"{team['reputation']:.2f}",
            f"{team['marketShare']:.4f}",
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="practenture_{code}_leaderboard.csv"'
        },
    )
