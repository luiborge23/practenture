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

    async def connect(self, websocket: WebSocket, session_code: str) -> None:
        """Accept a WebSocket connection for a specific session."""
        await websocket.accept()
        if session_code not in self.active_connections:
            self.active_connections[session_code] = set()
        self.active_connections[session_code].add(websocket)
        self.connection_map[websocket] = session_code

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        session_code = self.connection_map.pop(websocket, None)
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
        for connection in self.active_connections[session_code]:
            try:
                await connection.send_text(serialized)
            except (WebSocketDisconnect, RuntimeError):
                disconnected.add(connection)
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    def get_connection_count(self, session_code: str) -> int:
        """Get the number of active WebSocket connections for a session."""
        return len(self.active_connections.get(session_code, set()))


# Module-level singleton
manager = ConnectionManager()
