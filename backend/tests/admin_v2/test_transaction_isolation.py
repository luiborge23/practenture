"""Regression contracts for Admin V2 SQLite connection ownership."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import sqlite3
import threading
import uuid

import pytest

from admin_v2.repository import AdminSessionRepository
from database import db


TIMEOUT = 5


def _result(future: Future):
    return future.result(timeout=TIMEOUT)


def test_repository_transaction_uses_a_separate_connection_and_closes_it():
    repository = AdminSessionRepository(db)
    legacy_connection = db._get_conn()

    with repository._transaction() as transaction_connection:
        assert transaction_connection is not legacy_connection
        assert transaction_connection.row_factory is sqlite3.Row
        assert transaction_connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert transaction_connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        transaction_connection.execute("SELECT 1")


def test_repository_transaction_rolls_back_on_its_owned_connection():
    repository = AdminSessionRepository(db)
    identity = f"owned-rollback-{uuid.uuid4().hex}"
    client = "192.0.2.41"

    with pytest.raises(RuntimeError, match="force rollback"):
        with repository._transaction() as conn:
            conn.execute(
                """INSERT INTO privileged_login_attempts
                       (identity_key, client_key, attempt_count, window_started_at,
                        locked_until, last_attempt_at)
                   VALUES (?, ?, 1, 100, NULL, 100)""",
                (identity, client),
            )
            raise RuntimeError("force rollback")

    observer = db.connect()
    try:
        assert observer.execute(
            "SELECT 1 FROM privileged_login_attempts WHERE identity_key=? AND client_key=?",
            (identity, client),
        ).fetchone() is None
    finally:
        observer.close()


def test_admin_rollback_is_isolated_from_concurrent_legacy_writer():
    """A legacy commit cannot commit another thread's Admin V2 unit of work."""
    repository = AdminSessionRepository(db)
    identity = f"mixed-rollback-{uuid.uuid4().hex}"
    client = "198.51.100.77"
    username = f"mixed-writer-{uuid.uuid4().hex}"
    original_hash = "original-hash"
    updated_hash = "updated-by-legacy-writer"
    assert db.create_user(username, original_hash, "owner", "Mixed Writer")

    interleave = threading.Barrier(2, timeout=TIMEOUT)
    legacy_statement_started = threading.Event()
    legacy_writer_finished = threading.Event()
    legacy_connection = db._get_conn()

    def trace(statement: str) -> None:
        if statement.startswith("UPDATE users SET password_hash="):
            legacy_statement_started.set()

    def admin_transaction() -> None:
        with repository._transaction() as conn:
            conn.execute(
                """INSERT INTO privileged_login_attempts
                       (identity_key, client_key, attempt_count, window_started_at,
                        locked_until, last_attempt_at)
                   VALUES (?, ?, 1, 200, NULL, 200)""",
                (identity, client),
            )
            interleave.wait()
            assert legacy_statement_started.wait(TIMEOUT)
            # BEGIN IMMEDIATE owns the write lock, so the independent legacy
            # write cannot finish until this transaction rolls back.
            assert not legacy_writer_finished.is_set()
            raise RuntimeError("forced Admin V2 rollback")

    def legacy_writer() -> bool:
        interleave.wait()
        try:
            return db.update_user_password(username, updated_hash)
        finally:
            legacy_writer_finished.set()

    legacy_connection.set_trace_callback(trace)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            admin_future = pool.submit(admin_transaction)
            legacy_future = pool.submit(legacy_writer)
            with pytest.raises(RuntimeError, match="forced Admin V2 rollback"):
                _result(admin_future)
            assert _result(legacy_future) is True
    finally:
        legacy_connection.set_trace_callback(None)

    observer = db.connect()
    try:
        assert observer.execute(
            "SELECT 1 FROM privileged_login_attempts WHERE identity_key=? AND client_key=?",
            (identity, client),
        ).fetchone() is None
        user = observer.execute(
            "SELECT password_hash FROM users WHERE username=?", (username,)
        ).fetchone()
        assert user["password_hash"] == updated_hash
        observer.execute("DELETE FROM users WHERE username=?", (username,))
        observer.commit()
    finally:
        observer.close()