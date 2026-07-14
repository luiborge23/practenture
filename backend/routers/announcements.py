"""Announcement endpoints."""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
async def create_announcement(code: str, req: CreateAnnouncementRequest):
    """Professor sends an announcement to all teams in the session."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    announcement = Announcement(
        id=str(uuid.uuid4()),
        sessionId=session.id,
        message=req.message,
        authorId=req.authorId,
        authorName=req.authorName,
    )
    db.add_announcement(code, announcement)
    return CreateAnnouncementResponse(announcementId=announcement.id)


@router.get("/{code}/announcements")
async def get_announcements(code: str):
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
