"""Shared authorization rules for session-scoped reads and real-time streams."""

from fastapi import HTTPException

from database import db
from models import Session


def can_read_session(session: Session, user: dict) -> bool:
    """Return whether an authenticated principal participates in this session."""
    role = user.get("role")
    subject = user.get("sub")
    if role == "owner":
        return bool(subject)
    if role == "professor":
        return bool(subject) and db.get_session_professor_user_id(session.code) == subject
    if role == "student":
        return bool(subject) and any(
            not team.isAI and team.studentId == subject for team in session.teams
        )
    return False


def require_session_reader(session: Session, user: dict) -> None:
    """Fail closed unless the principal owns or participates in the session."""
    if not can_read_session(session, user):
        raise HTTPException(status_code=403, detail="Session access denied")
