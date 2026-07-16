"""Leaderboard endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from database import db
from models import LeaderboardEntry

router = APIRouter(prefix="/api/sessions", tags=["leaderboard"])


class LeaderboardResponse(BaseModel):
    sessionId: str
    round: int
    leaderboard: list[LeaderboardEntry]


@router.get("/{code}/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(code: str, user=Depends(get_current_user)):
    """Get current leaderboard sorted by total investor score."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if user.get("role") in ("professor", "owner"):
        if user.get("role") != "owner" and db.get_session_professor_user_id(code) != user.get("sub"):
            raise HTTPException(status_code=403, detail="Not your session")
    elif user.get("role") == "student":
        if not any(not team.isAI and team.studentId == user.get("sub") for team in session.teams):
            raise HTTPException(status_code=403, detail="Not enrolled in session")
    else:
        raise HTTPException(status_code=403, detail="Access denied")

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
        # Sort by name and assign ranks in the final displayed order.
        entries.sort(key=lambda e: e.teamName)
        for i, entry in enumerate(entries):
            entry.rank = i + 1
        return LeaderboardResponse(
            sessionId=session.id,
            round=session.currentRound,
            leaderboard=entries,
        )

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
                    "marketShare": 0.0,
                }
            team_scores[r.teamId]["totalScore"] = r.totalScore
            team_scores[r.teamId]["EPS"] = r.eps
            team_scores[r.teamId]["ROE"] = r.roe
            team_scores[r.teamId]["stockPrice"] = r.stockPrice
            team_scores[r.teamId]["imageRating"] = r.reputation
            team_scores[r.teamId]["creditRating"] = r.creditScore
            team_scores[r.teamId]["cumulativeProfit"] = r.cumulativeProfit
            team_scores[r.teamId]["marketShare"] = r.marketShare

    # Build entries
    entries = []
    for team in session.teams:
        score = team_scores.get(team.teamName, {})
        entries.append(LeaderboardEntry(
            teamName=team.teamName,
            studentName=team.studentId,
            totalScore=score.get("totalScore", 0.0),
            eps=score.get("EPS", 0.0),
            roe=score.get("ROE", 0.0),
            stockPrice=score.get("stockPrice", 0.0),
            imageRating=score.get("imageRating", 0.0),
            creditRating=score.get("creditRating", 0.0),
            cumulativeProfit=score.get("cumulativeProfit", 0.0),
            marketShare=score.get("marketShare", 0.0),
            rank=0,  # Will be set below
        ))

    # Sort by total score descending
    entries.sort(key=lambda e: e.totalScore, reverse=True)

    # Assign ranks
    for i, entry in enumerate(entries):
        entry.rank = i + 1

    return LeaderboardResponse(
        sessionId=session.id,
        round=session.currentRound,
        leaderboard=entries,
    )
