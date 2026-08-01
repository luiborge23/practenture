"""WebSocket manager for real-time session updates.

Handles:
- Professor: broadcast round results, session state changes
- Students: receive live updates when results are published
- Room-based: students only receive updates for their session code
"""

from __future__ import annotations

import json
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """Manages WebSocket connections per session code."""

    def __init__(self) -> None:
        # session_code → set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # WebSocket → session_code (for cleanup)
        self.connection_map: Dict[WebSocket, str] = {}
        # Keep the credential boundary with each socket so broadcasts can
        # reject expired, revoked, suspended, or no-longer-enrolled clients.
        self.connection_tokens: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, session_code: str, token: str) -> None:
        """Accept a WebSocket connection for a specific session."""
        await websocket.accept()
        if session_code not in self.active_connections:
            self.active_connections[session_code] = set()
        self.active_connections[session_code].add(websocket)
        self.connection_map[websocket] = session_code
        self.connection_tokens[websocket] = token

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        session_code = self.connection_map.pop(websocket, None)
        self.connection_tokens.pop(websocket, None)
        if session_code and session_code in self.active_connections:
            self.active_connections[session_code].discard(websocket)
            if not self.active_connections[session_code]:
                del self.active_connections[session_code]

    async def broadcast(self, session_code: str, message: dict) -> None:
        """Send a message to all connected clients in a session."""
        if session_code not in self.active_connections:
            return
        serialized = json.dumps(message, default=str)
        disconnected = set()
        for connection in tuple(self.active_connections[session_code]):
            try:
                # Lazy imports avoid coupling router import order to the
                # module-level manager singleton.
                from auth import verify_current_token
                from database import db
                from session_access import can_read_session

                token = self.connection_tokens.get(connection, "")
                try:
                    payload = verify_current_token(token)
                except Exception:
                    payload = None
                session = db.get_session(session_code)
                if payload is None or session is None or not can_read_session(session, payload):
                    await connection.close(code=4001, reason="Authentication expired")
                    disconnected.add(connection)
                    continue
                await connection.send_text(serialized)
            # Broadcasting is best-effort after the authoritative mutation has
            # committed. Any per-socket transport/auth failure must be isolated
            # so one racing disconnect cannot turn that REST mutation into a 500.
            except Exception:
                disconnected.add(connection)
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    def get_connection_count(self, session_code: str) -> int:
        """Get the number of active WebSocket connections for a session."""
        return len(self.active_connections.get(session_code, set()))


# Module-level singleton
manager = ConnectionManager()
