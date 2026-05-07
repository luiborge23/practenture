"""Leaderboard endpoint."""

from fastapi import APIRouter, HTTPException

from database import db
from models import LeaderboardEntry

router = APIRouter(prefix="/api/sessions", tags=["leaderboard"])


@router.get("/{code}/leaderboard")
async def get_leaderboard(code: str):
    """Get current leaderboard sorted by total investor score."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    all_results = db.get_all_results(code)
    if not all_results:
        # No rounds played yet — return empty or initial state
        entries = []
        for team in session.teams:
            entries.append(LeaderboardEntry(
                teamName=team.teamName,
                studentName=team.studentId,
                rank=len(entries) + 1,
            ))
        # Sort by name if no results
        entries.sort(key=lambda e: e.teamName)
        return {"sessionId": session.id, "round": session.currentRound, "leaderboard": entries}

    # Aggregate results per team
    team_scores: dict = {}
    for round_num, results in sorted(all_results.items()):
        for r in results:
            if r.teamId not in team_scores:
                team_scores[r.teamId] = {
                    "totalScore": 0.0,
                    "EPS": 0.0,
                    "ROE": 0.0,
                    "stockPrice": 0.0,
                    "imageRating": 0.0,
                    "creditRating": 0.0,
                    "cumulativeProfit": 0.0,
                }
            team_scores[r.teamId]["totalScore"] = r.totalScore
            team_scores[r.teamId]["EPS"] = r.eps
            team_scores[r.teamId]["ROE"] = r.roe
            team_scores[r.teamId]["stockPrice"] = r.stockPrice
            team_scores[r.teamId]["imageRating"] = r.reputation
            team_scores[r.teamId]["creditRating"] = r.creditScore
            team_scores[r.teamId]["cumulativeProfit"] = r.cumulativeProfit

    # Build entries
    entries = []
    for team in session.teams:
        score = team_scores.get(team.teamName, {})
        entries.append(LeaderboardEntry(
            teamName=team.teamName,
            studentName=team.studentId,
            totalScore=score.get("totalScore", 0.0),
            EPS=score.get("EPS", 0.0),
            ROE=score.get("ROE", 0.0),
            stockPrice=score.get("stockPrice", 0.0),
            imageRating=score.get("imageRating", 0.0),
            creditRating=score.get("creditRating", 0.0),
            cumulativeProfit=score.get("cumulativeProfit", 0.0),
            rank=0,  # Will be set below
        ))

    # Sort by total score descending
    entries.sort(key=lambda e: e.totalScore, reverse=True)

    # Assign ranks
    for i, entry in enumerate(entries):
        entry.rank = i + 1

    return {
        "sessionId": session.id,
        "round": session.currentRound,
        "leaderboard": entries,
    }
