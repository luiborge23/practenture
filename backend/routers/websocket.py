"""WebSocket endpoint for Practenture real-time updates."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from auth import verify_current_token
from database import db
from session_access import can_read_session
from ws_manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{code}")
async def websocket_endpoint(
    websocket: WebSocket,
    code: str,
):
    """WebSocket endpoint for real-time session updates.
    
    Clients connect with the session code to receive live updates.
    JWT token must be passed via the Authorization header (Bearer scheme).
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
    
    authorization = websocket.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or " " in token:
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    # Verify JWT token
    try:
        payload = verify_current_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid token or account state")
        return
    
    role = payload.get("role")
    if not can_read_session(session, payload):
        await websocket.close(code=4003, reason="Access denied")
        return
    
    # Accept connection and register
    await manager.connect(websocket, code, token)
    
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
                current_payload = verify_current_token(token)
            except Exception:
                current_payload = None
            current_session = db.get_session(code)
            if (
                current_payload is None
                or current_session is None
                or not can_read_session(current_session, current_payload)
            ):
                await websocket.close(code=4001, reason="Authentication expired")
                return
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue
            
            msg_type = message.get("type")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif msg_type == "request_status":
                current = db.get_session(code)
                if current is None:
                    await websocket.close(code=4004, reason="Session not found")
                    return
                status = {
                    "sessionId": current.id,
                    "code": current.code,
                    "state": current.state.value,
                    "currentRound": current.currentRound,
                    "totalRounds": current.config.totalRounds,
                    "teamCount": len(current.teams),
                    "submittedCount": db.count_submitted_decisions(code, current.currentRound) if current.currentRound > 0 else 0,
                }
                await websocket.send_json({"type": "status", **status})
            
            else:
                await websocket.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
        await websocket.close(code=1011, reason="Internal server error")
