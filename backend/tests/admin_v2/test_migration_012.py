"""Execution-level verification for legacy SES correlation backfill 012."""
from __future__ import annotations

from importlib import import_module
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from ses_suppression import (
    SES_FEEDBACK_CORRELATION_RETENTION,
    recipient_suppression_hash,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
SUPPRESSION_KEY = "42" * 32
migration_012 = import_module(
    "migrations.versions.012_backfill_legacy_ses_feedback_correlations"
)


def _config(path: Path) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
    return config


def _at_011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str):
    path = tmp_path / name
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("PRACTENTURE_EMAIL_SUPPRESSION_KEY", SUPPRESSION_KEY)
    config = _config(path)
    command.upgrade(config, "011")
    return path, config


def _delivery(
    delivery_id: str,
    *,
    email: str = "Legacy.Professor@Example.edu ",
    state: str = "accepted",
    provider: str | None = "ses",
    message_id: str | None = "ses-legacy-message",
    updated_at: str = "2025-02-03T04:05:06+00:00",
) -> tuple[object, ...]:
    return (
        delivery_id,
        "invitation-legacy",
        email,
        "owner-legacy",
        f"key-{delivery_id}",
        f"fingerprint-{delivery_id}",
        state,
        provider,
        message_id,
        None if state == "accepted" else "failure",
        "2025-02-03T04:00:00+00:00",
        updated_at,
    )


def _insert_delivery(conn: sqlite3.Connection, row: tuple[object, ...]) -> None:
    conn.execute(
        """INSERT INTO invitation_email_deliveries
           (id, invitation_id, recipient_email, owner_id, idempotency_key_hash,
            request_fingerprint, state, provider, provider_message_id, failed_code,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        row,
    )


def _expected(email: str, message_id: str, accepted_at: str) -> tuple[str, ...]:
    accepted = datetime.fromisoformat(accepted_at).astimezone(timezone.utc)
    recipient_hash = recipient_suppression_hash(email, required=True)
    assert recipient_hash is not None
    return (
        "ses",
        message_id,
        recipient_hash,
        accepted.isoformat(),
        (accepted + SES_FEEDBACK_CORRELATION_RETENTION).isoformat(),
    )


def test_migration_012_backfills_only_hmac_correlation_with_365_day_expiry(
    tmp_path, monkeypatch
):
    path, config = _at_011(tmp_path, monkeypatch, "success.sqlite3")
    row = _delivery("delivery-success")
    with sqlite3.connect(path) as conn:
        _insert_delivery(conn, row)
        conn.commit()

    command.upgrade(config, "012")

    expected = _expected(str(row[2]), str(row[8]), str(row[11]))
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("012",)
        columns = [
            item[1] for item in conn.execute("PRAGMA table_info(ses_feedback_correlations)")
        ]
        assert columns == [
            "provider",
            "provider_message_id",
            "recipient_hash",
            "accepted_at",
            "feedback_expires_at",
        ]
        stored = conn.execute(
            """SELECT provider, provider_message_id, recipient_hash, accepted_at,
                      feedback_expires_at FROM ses_feedback_correlations"""
        ).fetchone()
        assert stored == expected
        assert str(row[2]) not in repr(stored)
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='ses_feedback_correlations'"
        ).fetchone()[0].casefold()
        for forbidden in ("email", "invitation", "user", "foreign key"):
            assert forbidden not in ddl

    accepted = datetime.fromisoformat(expected[3])
    expires = datetime.fromisoformat(expected[4])
    assert expires - accepted == timedelta(days=365)


def test_migration_012_missing_suppression_key_fails_and_rolls_back(tmp_path, monkeypatch):
    path, config = _at_011(tmp_path, monkeypatch, "missing-key.sqlite3")
    with sqlite3.connect(path) as conn:
        _insert_delivery(conn, _delivery("delivery-a"))
        conn.commit()
    monkeypatch.delenv("PRACTENTURE_EMAIL_SUPPRESSION_KEY")

    with pytest.raises(RuntimeError, match="suppression key is not configured"):
        command.upgrade(config, "012")

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("011",)
        assert conn.execute("SELECT COUNT(*) FROM ses_feedback_correlations").fetchone() == (0,)


def test_migration_012_existing_exact_row_is_idempotent(tmp_path, monkeypatch):
    path, config = _at_011(tmp_path, monkeypatch, "exact.sqlite3")
    row = _delivery("delivery-exact")
    expected = _expected(str(row[2]), str(row[8]), str(row[11]))
    with sqlite3.connect(path) as conn:
        _insert_delivery(conn, row)
        conn.execute(
            "INSERT INTO ses_feedback_correlations VALUES (?, ?, ?, ?, ?)", expected
        )
        conn.commit()

    command.upgrade(config, "012")

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM ses_feedback_correlations").fetchone() == (1,)
        assert conn.execute("SELECT * FROM ses_feedback_correlations").fetchone() == expected


def test_migration_012_collision_mismatch_fails_and_rolls_back(tmp_path, monkeypatch):
    path, config = _at_011(tmp_path, monkeypatch, "collision.sqlite3")
    first = _delivery("a-valid", message_id="ses-first")
    collision = _delivery("b-collision", message_id="ses-collision")
    mismatched = list(_expected(str(collision[2]), str(collision[8]), str(collision[11])))
    mismatched[2] = "f" * 64
    with sqlite3.connect(path) as conn:
        _insert_delivery(conn, first)
        _insert_delivery(conn, collision)
        conn.execute(
            "INSERT INTO ses_feedback_correlations VALUES (?, ?, ?, ?, ?)", mismatched
        )
        conn.commit()

    with pytest.raises(RuntimeError, match="does not match legacy delivery"):
        command.upgrade(config, "012")

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("011",)
        assert conn.execute("SELECT * FROM ses_feedback_correlations").fetchall() == [tuple(mismatched)]


def test_migration_012_ignores_ineligible_deliveries(tmp_path, monkeypatch):
    path, config = _at_011(tmp_path, monkeypatch, "filters.sqlite3")
    rows = [
        _delivery("pending", state="pending", updated_at="malformed"),
        _delivery("failed", state="failed", updated_at="malformed"),
        _delivery("other-provider", provider="other", updated_at="malformed"),
        _delivery("null-message", message_id=None, updated_at="malformed"),
        _delivery("empty-message", message_id="", updated_at="malformed"),
        _delivery("blank-message", message_id="   ", updated_at="malformed"),
        _delivery("eligible", message_id="ses-eligible"),
    ]
    with sqlite3.connect(path) as conn:
        for row in rows:
            _insert_delivery(conn, row)
        conn.commit()

    command.upgrade(config, "012")

    with sqlite3.connect(path) as conn:
        assert conn.execute(
            "SELECT provider_message_id FROM ses_feedback_correlations"
        ).fetchall() == [("ses-eligible",)]


def test_migration_012_malformed_required_timestamp_fails_and_rolls_back(
    tmp_path, monkeypatch
):
    path, config = _at_011(tmp_path, monkeypatch, "malformed.sqlite3")
    with sqlite3.connect(path) as conn:
        _insert_delivery(conn, _delivery("a-valid", message_id="ses-valid"))
        _insert_delivery(
            conn,
            _delivery("b-malformed", message_id="ses-malformed", updated_at="2025-02-03 04:05:06"),
        )
        conn.commit()

    with pytest.raises(RuntimeError, match="invalid acceptance timestamp"):
        command.upgrade(config, "012")

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("011",)
        assert conn.execute("SELECT COUNT(*) FROM ses_feedback_correlations").fetchone() == (0,)


@pytest.mark.parametrize("recipient", ["", "   "])
def test_migration_012_invalid_required_recipient_fails_and_rolls_back(
    tmp_path, monkeypatch, recipient
):
    path, config = _at_011(tmp_path, monkeypatch, f"recipient-{repr(recipient)}.sqlite3")
    valid = _delivery("a-valid", message_id="ses-valid")
    invalid = list(_delivery("b-invalid", message_id="ses-invalid"))
    invalid[2] = recipient
    with sqlite3.connect(path) as conn:
        _insert_delivery(conn, valid)
        _insert_delivery(conn, tuple(invalid))
        conn.commit()

    with pytest.raises(RuntimeError, match="invalid recipient"):
        command.upgrade(config, "012")

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("011",)
        assert conn.execute("SELECT COUNT(*) FROM ses_feedback_correlations").fetchone() == (0,)


@pytest.mark.parametrize("recipient", [None, 123])
def test_migration_012_rejects_non_string_recipient_before_hashing(recipient):
    with pytest.raises(RuntimeError, match="invalid recipient"):
        migration_012._recipient_hash(recipient)


def test_migration_chain_reaches_012_and_noop_downgrade_preserves_backfill(
    tmp_path, monkeypatch
):
    path, config = _at_011(tmp_path, monkeypatch, "chain.sqlite3")
    row = _delivery("delivery-chain", message_id="ses-chain")
    with sqlite3.connect(path) as conn:
        _insert_delivery(conn, row)
        conn.commit()

    command.upgrade(config, "head")
    command.downgrade(config, "011")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("011",)
        assert conn.execute("SELECT * FROM ses_feedback_correlations").fetchone() == _expected(
            str(row[2]), str(row[8]), str(row[11])
        )

    command.upgrade(config, "head")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("012",)
        assert conn.execute("SELECT COUNT(*) FROM ses_feedback_correlations").fetchone() == (1,)
