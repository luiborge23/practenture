#!/usr/bin/env python3
"""Live authenticated WebSocket admission, isolation, fan-out, and reconnect QA."""
from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.request

import websockets
from websockets.exceptions import InvalidStatus

BASE = os.environ.get("PRACTENTURE_E2E_BASE_URL", "http://127.0.0.1:18005").rstrip("/")
WS_BASE = BASE.replace("http://", "ws://").replace("https://", "wss://")


def request(method: str, path: str, payload=None, token: str | None = None, expected=(200,)):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw, status = response.read(), response.status
    except urllib.error.HTTPError as exc:
        raw, status = exc.read(), exc.code
    if status not in expected:
        raise AssertionError(f"{method} {path}: HTTP {status}: {raw[:500]!r}")
    return json.loads(raw) if raw else None


def token_from(body: dict) -> str:
    token = body.get("accessToken") or body.get("access_token")
    assert token
    return token


async def receive_type(socket, expected_type: str) -> dict:
    body = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))
    assert body.get("type") == expected_type, body
    return body


async def assert_denied(code: str, token: str | None, expected_status: int = 403) -> None:
    headers = {} if token is None else {"Authorization": "Bearer " + token}
    try:
        async with websockets.connect(
            f"{WS_BASE}/ws/{code}", additional_headers=headers
        ) as socket:
            await socket.recv()
    except InvalidStatus as exc:
        assert exc.response.status_code == expected_status, exc
        return
    raise AssertionError(
        f"WebSocket admission unexpectedly succeeded; expected HTTP {expected_status}"
    )


async def main() -> None:
    professor_user = os.environ.get("PRACTENTURE_PROFESSOR_USERNAME", "local-e2e-professor")
    professor_password = os.environ["PRACTENTURE_PROFESSOR_PASSWORD"]
    professor = request("POST", "/api/auth/login", {
        "username": professor_user,
        "password": professor_password,
        "provider": "password",
    })
    assert isinstance(professor, dict)
    professor_token = token_from(professor)
    stamp = str(int(time.time() * 1000))

    class_row = request("POST", "/api/classes", {
        "name": "WebSocket E2E " + stamp,
        "description": "Disposable real-time qualification",
    }, token=professor_token, expected=(201,))
    assert isinstance(class_row, dict)

    students: list[tuple[str, str]] = []
    for suffix in ("A", "B"):
        student_id = f"WS{stamp}{suffix}"
        registration = request("POST", "/api/auth/register", {
            "student_id": student_id,
            "name": f"WebSocket Student {suffix}",
            "password": "LocalStudent1!",
        }, expected=(201,))
        assert isinstance(registration, dict)
        student_token = token_from(registration)
        request("POST", "/api/classes/join", {"join_code": class_row["join_code"]},
                token=student_token)
        students.append((student_id, student_token))

    sessions: list[str] = []
    for index, (student_id, student_token) in enumerate(students, 1):
        created = request("POST", "/api/sessions", {
            "config": {"totalRounds": 2, "numberOfAICompetitors": 0},
            "teams": [],
            "maxHumanTeams": 2,
            "classId": class_row["id"],
        }, token=professor_token, expected=(201,))
        assert isinstance(created, dict)
        code = created["code"]
        request("PUT", f"/api/sessions/{code}/join", {
            "teamName": f"WS-Team-{index}", "studentId": student_id,
        }, token=student_token)
        sessions.append(code)

    code_a, code_b = sessions
    student_a_token = students[0][1]
    student_b_token = students[1][1]
    try:
        await assert_denied(code_a, None)
        await assert_denied(code_a, student_b_token)

        auth_professor = {"Authorization": "Bearer " + professor_token}
        auth_student_a = {"Authorization": "Bearer " + student_a_token}
        async with (
            websockets.connect(f"{WS_BASE}/ws/{code_a}", additional_headers=auth_professor) as professor_a,
            websockets.connect(f"{WS_BASE}/ws/{code_a}", additional_headers=auth_student_a) as student_a,
            websockets.connect(f"{WS_BASE}/ws/{code_b}", additional_headers=auth_professor) as professor_b,
        ):
            assert (await receive_type(professor_a, "connected"))["role"] == "professor"
            assert (await receive_type(student_a, "connected"))["role"] == "student"
            await receive_type(professor_b, "connected")

            await student_a.send(json.dumps({"type": "ping"}))
            await receive_type(student_a, "pong")
            await student_a.send(json.dumps({"type": "request_status"}))
            initial_status = await receive_type(student_a, "status")
            assert initial_status["state"] == "creating"

            request("POST", f"/api/sessions/{code_a}/start", token=professor_token)
            professor_event = await receive_type(professor_a, "session_started")
            student_event = await receive_type(student_a, "session_started")
            assert professor_event["code"] == code_a == student_event["code"]
            try:
                leaked = await asyncio.wait_for(professor_b.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
            else:
                raise AssertionError(f"Room B received room A event: {leaked}")

        async with websockets.connect(
            f"{WS_BASE}/ws/{code_a}", additional_headers=auth_student_a
        ) as reconnected:
            welcome = await receive_type(reconnected, "connected")
            assert welcome["state"] == "active" and welcome["currentRound"] == 1
            await reconnected.send(json.dumps({"type": "request_status"}))
            status = await receive_type(reconnected, "status")
            assert status["state"] == "active" and status["currentRound"] == 1

        print(json.dumps({
            "status": "PASS",
            "authenticatedAdmissions": 4,
            "deniedMissingAuth": 1,
            "deniedForeignStudent": 1,
            "sequentialFrames": ["connected", "pong", "status", "session_started"],
            "fanoutRecipients": 2,
            "roomIsolation": "PASS",
            "reconnectState": "active-round-1",
        }, sort_keys=True))
    finally:
        for code in sessions:
            request("DELETE", f"/api/sessions/{code}", token=professor_token,
                    expected=(204, 404))


if __name__ == "__main__":
    asyncio.run(main())
