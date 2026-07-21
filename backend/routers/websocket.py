"""WebSocket endpoint for BizSimAI real-time updates."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth import _verify_token, verify_student_or_professor
from database import db
from ws_manager import manager

router = APIRouter(tags=["websocket"])
http_bearer = HTTPBearer(auto_error=False)


@router.websocket("/ws/{code}")
async def websocket_endpoint(
    websocket: WebSocket,
    code: str,
    credentials: HTTPAuthorizationCredentials = None,
):
    """WebSocket endpoint for real-time session updates.
    
    Clients connect with the session code to receive live updates.
    JWT token can be passed via Authorization header (Bearer scheme) or query param.
    Supported message types:
    - {"type": "join", "teamId": "..."} — identify as a team
    - {"type": "ping"} — keepalive
    - {"type": "request_status"} — request current session status
    """
    # Verify the session exists
    session = db.get_session(code)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return
    
    # Verify authentication (token in Authorization header or query param)
    token = None
    if credentials and credentials.credentials:
        # Use Authorization header (preferred, SOTA: no token in URL)
        token = credentials.credentials
    else:
        # Fallback to query param for backward compatibility
        token = websocket.query_params.get("token")
    
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    # Verify JWT token
    payload = _verify_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    role = payload.get("role")
    if role not in ("professor", "student"):
        await websocket.close(code=4003, reason="Access denied")
        return
    
    # Accept connection and register
    await manager.connect(websocket, code)
    
    # Send welcome message
    await websocket.send_json({
        "type": "connected",
        "sessionId": session.id,
        "code": session.code,
        "role": role,
        "currentRound": session.currentRound,
        "state": session.state.value,
        "teamCount": len(session.teams),
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue
            
            msg_type = message.get("type")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif msg_type == "request_status":
                # Send current session status
                status = {
                    "sessionId": session.id,
                    "code": session.code,
                    "state": session.state.value,
                    "currentRound": session.currentRound,
                    "totalRounds": session.config.totalRounds,
                    "teamCount": len(session.teams),
                    "submittedCount": db.count_submitted_decisions(code, session.currentRound) if session.currentRound > 0 else 0,
                }
                await websocket.send_json({"type": "status", **status})
            
            else:
                await websocket.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        raise HTTPException(status_code=500, detail=str(e))
