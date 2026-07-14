"""Dashboard endpoints for professor overview — filtered by logged-in professor."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user
from database import db
from models import DashboardSessionResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class DashboardSessionListResponse(BaseModel):
    sessions: list[DashboardSessionResponse]


@router.get("/sessions", response_model=DashboardSessionListResponse)
async def get_dashboard_sessions(user=Depends(get_current_user)):
    """Get sessions for the dashboard, filtered by the logged-in professor.

    - Owner: sees all sessions
    - Professor: sees only their sessions (by professor_user_id)
    - Student: sees sessions for their enrolled classes
    """
    role = user.get("role")
    user_id = user.get("sub")

    if role == "owner":
        sessions = db.list_sessions()
    elif role == "professor":
        sessions = db.list_sessions(professor_user_id=user_id)
    elif role == "student":
        # Student sees sessions for classes they're enrolled in
        classes = db.get_student_classes(user_id)
        sessions = []
        for cls in classes:
            sessions.extend(db.list_sessions(class_id=cls["id"]))
    else:
        sessions = []

    result: list[DashboardSessionResponse] = []
    for s in sessions:
        total_submissions = 0
        for r in range(1, s.config.totalRounds + 1):
            total_submissions += len(db.decisions.get(s.code, {}).get(r, {}))
        ai_count = sum(1 for t in s.teams if getattr(t, "isAI", False))
        state_str = s.state.value if hasattr(s.state, "value") else str(s.state)
        result.append(DashboardSessionResponse(
            code=s.code,
            state=state_str,
            currentRound=s.currentRound,
            totalRounds=s.config.totalRounds,
            teamsCount=len(s.teams) - ai_count,
            aiTeamsCount=ai_count,
            totalTeams=len(s.teams),
            totalSubmissions=total_submissions,
            lastRound=s.currentRound,
        ))
    return DashboardSessionListResponse(sessions=result)
