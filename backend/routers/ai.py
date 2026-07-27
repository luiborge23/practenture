"""Practenture AI Router — Bedrock-powered endpoints.

Endpoints:
  POST /api/ai/scenario          — Generate business scenario (professor)
  POST /api/ai/feedback          — Get feedback on student decision
  POST /api/ai/hint              — Get smart hint/recommendation
  POST /api/ai/insights          — Professor dashboard AI insights
  GET  /api/ai/status            — Check Bedrock availability
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_service import (
    BEDROCK_MODEL,
    BEDROCK_REGION,
    BEDROCK_ENABLED,
    generate_scenario,
    provide_feedback,
    generate_hint,
    generate_insights,
)
from auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["AI"])


# ── Professor-only dependency ───────────────────────────────────────────────

def _require_professor(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require a valid JWT with professor/owner role."""
    if user.get("role") not in ("professor", "owner"):
        raise HTTPException(status_code=403, detail="Professor access required")
    return user


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/status")
async def ai_status():
    """Check Bedrock availability and configuration."""
    return {
        "enabled": BEDROCK_ENABLED,
        "model": BEDROCK_MODEL,
        "region": BEDROCK_REGION,
    }


@router.post("/scenario", response_model=Dict[str, Any])
async def post_scenario(
    request: Dict[str, Any],
    _professor = Depends(_require_professor),
):
    """Generate an AI business scenario for students.

    Body: industry, difficulty, round_num, total_rounds
    """
    try:
        scenario = generate_scenario(
            industry=request.get("industry", "consumer_electronics"),
            difficulty=request.get("difficulty", "medium"),
            round_num=request.get("round_num", 1),
            total_rounds=request.get("total_rounds", 20),
        )
        return {
            "scenario": scenario,
            "source": "ai" if BEDROCK_ENABLED else "fallback",
        }
    except Exception as e:
        logger.error("Scenario generation failed: %s", e)
        raise HTTPException(status_code=500, detail="AI service error")


@router.post("/feedback", response_model=Dict[str, Any])
async def post_feedback(
    request: Dict[str, Any],
    _professor = Depends(_require_professor),
):
    """Get educational feedback on a student's decision.

    Body: decision (dict), round_result (dict), context (str, optional)
    """
    try:
        feedback = provide_feedback(
            student_decision=request.get("decision", {}),
            round_result=request.get("round_result", {}),
            context=request.get("context", ""),
        )
        return {
            "feedback": feedback,
            "source": "ai" if BEDROCK_ENABLED else "fallback",
        }
    except Exception as e:
        logger.error("Feedback generation failed: %s", e)
        raise HTTPException(status_code=500, detail="AI service error")


@router.post("/hint", response_model=Dict[str, Any])
async def post_hint(
    request: Dict[str, Any],
    _professor = Depends(_require_professor),
):
    """Get a smart hint/recommendation for a student.

    Body: current_state (dict), problem (str, optional)
    """
    try:
        hint = generate_hint(
            current_state=request.get("current_state", {}),
            problem=request.get("problem", ""),
        )
        return {
            "hint": hint,
            "source": "ai" if BEDROCK_ENABLED else "fallback",
        }
    except Exception as e:
        logger.error("Hint generation failed: %s", e)
        raise HTTPException(status_code=500, detail="AI service error")


@router.post("/insights", response_model=Dict[str, Any])
async def post_insights(
    request: Dict[str, Any],
    _professor = Depends(_require_professor),
):
    """Generate professor-facing AI insights about simulation data.

    Body: session_results (list of dicts), team_count (int)
    """
    try:
        insights = generate_insights(
            session_results=request.get("session_results", []),
            team_count=request.get("team_count", 1),
        )
        return {
            "insights": insights,
            "source": "ai" if BEDROCK_ENABLED else "fallback",
        }
    except Exception as e:
        logger.error("Insights generation failed: %s", e)
        raise HTTPException(status_code=500, detail="AI service error")
