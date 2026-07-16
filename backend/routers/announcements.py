"""Announcement endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, verify_professor
from database import db
from models import (
    Announcement,
    CreateAnnouncementRequest,
    ErrorResponse,
)

router = APIRouter(prefix="/api/sessions", tags=["announcements"])


class CreateAnnouncementResponse(BaseModel):
    status: str = "sent"
    announcementId: str


class AnnouncementItem(BaseModel):
    id: str
    message: str
    authorId: str
    authorName: str
    timestamp: str


class GetAnnouncementsResponse(BaseModel):
    announcements: list[AnnouncementItem]


@router.post("/{code}/announcements", response_model=CreateAnnouncementResponse)
async def create_announcement(code: str, req: CreateAnnouncementRequest, user=Depends(verify_professor)):
    """Professor sends an announcement to all teams in the session."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if user.get("role") != "owner" and db.get_session_professor_user_id(code) != user.get("sub"):
        raise HTTPException(status_code=403, detail="Not your session")

    announcement = Announcement(
        id=str(uuid.uuid4()),
        sessionId=session.id,
        message=req.message,
        authorId=user["sub"],
        authorName=req.authorName,
    )
    db.add_announcement(code, announcement)
    return CreateAnnouncementResponse(announcementId=announcement.id)


@router.get("/{code}/announcements", response_model=list[Announcement])
async def get_announcements(code: str, user=Depends(get_current_user)):
    """Get all announcements for a session."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    announcements = db.get_announcements(code)
    return [
        {
            "id": a.id,
            "sessionId": a.sessionId,
            "message": a.message,
            "authorId": a.authorId,
            "authorName": a.authorName,
            "timestamp": a.timestamp.isoformat(),
        }
        for a in announcements
    ]
