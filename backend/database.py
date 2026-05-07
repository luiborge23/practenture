"""In-memory database for BizSimAI sessions."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from models import (
    Announcement,
    PlayerDecision,
    RoundResult,
    Session,
    SessionConfiguration,
    TeamConfig,
)


def _generate_code() -> str:
    """Generate a random 8-char alphanumeric code for sessions (BIZ-XXXX)."""
    chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "BIZ-" + "".join(secrets.choice(chars) for _ in range(4))


def _generate_id() -> str:
    return secrets.token_hex(8)


class Database:
    """In-memory store for sessions, decisions, announcements, and results."""

    def __init__(self) -> None:
        self.sessions: Dict[str, Session] = {}       # code → Session
        self.decisions: Dict[str, Dict[int, Dict[str, PlayerDecision]]] = {}  # code → round → teamId → decision
        self.announcements: Dict[str, List[Announcement]] = {}  # code → list
        self.results: Dict[str, Dict[int, List[RoundResult]]] = {}  # code → round → [RoundResult]
        self.team_states: Dict[str, Dict[str, Dict[str, Any]]] = {}  # code → teamId → state

    def create_session(
        self,
        config: SessionConfiguration,
        teams: List[TeamConfig],
        created_by: str,
        max_human_teams: int = 30,
    ) -> str:
        code = _generate_code()
        # Ensure unique code
        while code in self.sessions:
            code = _generate_code()

        session = Session(
            id=_generate_id(),
            code=code,
            config=config,
            teams=teams,
            created_by=created_by,
            maxHumanTeams=max_human_teams,
        )
        self.sessions[code] = session
        self.decisions[code] = {}
        self.announcements[code] = []
        self.results[code] = {}
        self.team_states[code] = {}
        return code

    def get_session(self, code: str) -> Optional[Session]:
        return self.sessions.get(code)

    def update_session(self, code: str, updates: Dict[str, Any]) -> None:
        session = self.sessions.get(code)
        if session:
            for key, value in updates.items():
                setattr(session, key, value)

    def get_session_by_id(self, session_id: str) -> Optional[Session]:
        for s in self.sessions.values():
            if s.id == session_id:
                return s
        return None

    def add_announcement(self, session_id: str, announcement: Announcement) -> None:
        if session_id not in self.announcements:
            self.announcements[session_id] = []
        self.announcements[session_id].append(announcement)

    def get_announcements(self, session_id: str) -> List[Announcement]:
        return self.announcements.get(session_id, [])

    def store_decision(
        self, session_code: str, round_num: int, team_id: str, decision: PlayerDecision
    ) -> bool:
        if session_code not in self.decisions:
            return False
        if round_num not in self.decisions[session_code]:
            self.decisions[session_code][round_num] = {}
        # Prevent double submission
        if team_id in self.decisions[session_code][round_num]:
            return False
        self.decisions[session_code][round_num][team_id] = decision
        return True

    def get_decisions(self, session_code: str, round_num: int) -> Dict[str, PlayerDecision]:
        return self.decisions.get(session_code, {}).get(round_num, {})

    def has_decision(self, session_code: str, round_num: int, team_id: str) -> bool:
        return (
            session_code in self.decisions
            and round_num in self.decisions.get(session_code, {})
            and team_id in self.decisions[session_code].get(round_num, {})
        )

    def store_results(self, session_code: str, round_num: int, results: List[RoundResult]) -> None:
        if session_code not in self.results:
            self.results[session_code] = {}
        self.results[session_code][round_num] = results

    def get_results(self, session_code: str, round_num: int) -> Optional[List[RoundResult]]:
        return self.results.get(session_code, {}).get(round_num)

    def get_all_results(self, session_code: str) -> Dict[int, List[RoundResult]]:
        return self.results.get(session_code, {})

    def get_team_state(self, session_code: str, team_id: str) -> Dict[str, Any]:
        return self.team_states.get(session_code, {}).get(team_id, {})

    def update_team_state(
        self, session_code: str, team_id: str, updates: Dict[str, Any]
    ) -> None:
        if session_code not in self.team_states:
            self.team_states[session_code] = {}
        if team_id not in self.team_states[session_code]:
            self.team_states[session_code][team_id] = {}
        self.team_states[session_code][team_id].update(updates)

    def count_submitted_decisions(self, session_code: str, round_num: int) -> int:
        return len(self.decisions.get(session_code, {}).get(round_num, {}))

    def delete_session(self, code: str) -> bool:
        if code in self.sessions:
            del self.sessions[code]
            self.decisions.pop(code, None)
            self.announcements.pop(code, None)
            self.results.pop(code, None)
            self.team_states.pop(code, None)
            return True
        return False


# Module-level singleton
db = Database()
