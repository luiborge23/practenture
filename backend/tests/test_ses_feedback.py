from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import json
import os
from types import SimpleNamespace

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from admin_v2.errors import AdminError
from admin_v2.invitations_repository import InvitationRepository, hash_invitation_secret
from database import db
import ses_feedback
from ses_suppression import recipient_suppression_hash

TOPIC = "arn:aws:sns:us-east-1:123456789012:practenture-ses-feedback"
KEY = "11" * 32


@pytest.fixture(autouse=True)
def isolated_feedback(monkeypatch):
    monkeypatch.setenv("PRACTENTURE_SES_SNS_TOPIC_ARN", TOPIC)
    monkeypatch.setenv("PRACTENTURE_SES_REGION", "us-east-1")
    monkeypatch.setenv("PRACTENTURE_EMAIL_SUPPRESSION_KEY", KEY)
    conn = db.connect()
    try:
        for table in ("ses_feedback_events", "ses_recipient_suppressions", "ses_feedback_correlations", "invitation_email_deliveries"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM professor_invitations")
        conn.commit()
    finally:
        conn.close()
    yield


def _accepted_delivery(email="professor@example.edu", message_id="ses-message-1"):
    now = datetime.now(timezone.utc).isoformat()
    conn = db.connect()
    try:
        conn.execute("INSERT OR IGNORE INTO organizations (id, name, status) VALUES ('org-feedback', 'Feedback Org', 'active')")
        conn.execute(
            """INSERT INTO professor_invitations
               (id, secret_hash, masked_code, organization_id, intended_email, status,
                expires_at, max_uses, use_count, issued_by, created_at)
               VALUES ('inv-feedback', ?, 'abcd...wxyz', 'org-feedback', ?, 'active', ?, 1, 0, 'owner', ?)""",
            (hash_invitation_secret("one-time-secret"), email, (datetime.now(timezone.utc)+timedelta(days=1)).isoformat(), now),
        )
        conn.execute(
            """INSERT INTO invitation_email_deliveries
               (id, invitation_id, recipient_email, owner_id, idempotency_key_hash,
                request_fingerprint, state, provider, provider_message_id, created_at, updated_at)
               VALUES ('idel-feedback', 'inv-feedback', ?, 'owner', 'keyhash',
                       'fingerprint', 'accepted', 'ses', ?, ?, ?)""",
            (email, message_id, now, now),
        )
        conn.execute(
            """INSERT INTO ses_feedback_correlations
               (provider, provider_message_id, recipient_hash, accepted_at, feedback_expires_at)
               VALUES ('ses', ?, ?, ?, ?)""",
            (message_id, recipient_suppression_hash(email, required=True), now,
             (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _sns_message(kind="Bounce", bounce_type="Permanent", message_id="ses-message-1", sns_id="sns-1"):
    inner = {"notificationType": kind, "mail": {"messageId": message_id}}
    if kind == "Bounce":
        inner["bounce"] = {"bounceType": bounce_type}
    return {"MessageId": sns_id, "Message": json.dumps(inner)}


def test_permanent_bounce_hashes_recipient_revokes_and_is_idempotent():
    _accepted_delivery()
    assert ses_feedback.process_ses_feedback(_sns_message()) == "suppressed"
    assert ses_feedback.process_ses_feedback(_sns_message()) == "suppressed"
    conn = db.connect()
    try:
        suppression = conn.execute("SELECT recipient_hash, reason FROM ses_recipient_suppressions").fetchone()
        assert tuple(suppression) == (recipient_suppression_hash("professor@example.edu"), "permanent_bounce")
        assert "professor@example.edu" not in str(tuple(suppression))
        invitation = conn.execute("SELECT status, revoked_by FROM professor_invitations WHERE id='inv-feedback'").fetchone()
        assert tuple(invitation) == ("revoked", "ses-feedback")
        assert conn.execute("SELECT COUNT(*) FROM ses_feedback_events").fetchone()[0] == 1
        audit = conn.execute("SELECT metadata_json FROM admin_audit_events WHERE action='invitation.email_feedback'").fetchone()[0]
        assert "ses-message-1" not in audit
        assert "professor@example.edu" not in audit
        assert "providerMessageIdHash" in audit
    finally:
        conn.close()


def test_complaint_suppresses_but_transient_bounce_does_not():
    _accepted_delivery(message_id="transient")
    assert ses_feedback.process_ses_feedback(_sns_message(bounce_type="Transient", message_id="transient", sns_id="sns-transient")) == "ignored_transient"
    conn = db.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM ses_recipient_suppressions").fetchone()[0] == 0
        assert conn.execute("SELECT status FROM professor_invitations").fetchone()[0] == "active"
    finally:
        conn.close()
    assert ses_feedback.process_ses_feedback(_sns_message(kind="Complaint", message_id="transient", sns_id="sns-complaint")) == "suppressed"


def test_unknown_provider_message_is_recorded_without_suppression():
    assert ses_feedback.process_ses_feedback(_sns_message(message_id="unknown")) == "ignored_unknown"
    conn = db.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM ses_recipient_suppressions").fetchone()[0] == 0
    finally:
        conn.close()


def test_terminal_feedback_uses_correlation_after_delivery_and_invitation_are_deleted():
    _accepted_delivery(email="delayed@example.edu", message_id="delayed-message")
    conn = db.connect()
    try:
        conn.execute("DELETE FROM invitation_email_deliveries")
        conn.execute("DELETE FROM professor_invitations")
        conn.commit()
    finally:
        conn.close()
    payload = _sns_message(kind="Complaint", message_id="delayed-message", sns_id="sns-delayed")
    assert ses_feedback.process_ses_feedback(payload) == "suppressed"
    assert ses_feedback.process_ses_feedback(payload) == "suppressed"
    conn = db.connect()
    try:
        assert tuple(conn.execute(
            "SELECT recipient_hash, reason FROM ses_recipient_suppressions"
        ).fetchone()) == (recipient_suppression_hash("delayed@example.edu"), "complaint")
        assert conn.execute("SELECT COUNT(*) FROM ses_feedback_events").fetchone()[0] == 1
        correlation = conn.execute("SELECT * FROM ses_feedback_correlations").fetchone()
        assert "delayed@example.edu" not in str(tuple(correlation))
        audit = conn.execute("SELECT metadata_json FROM admin_audit_events WHERE action='invitation.email_feedback'").fetchone()[0]
        assert "delayed@example.edu" not in audit and "delayed-message" not in audit
    finally:
        conn.close()


def test_expired_correlation_is_ignored_unknown_without_suppression():
    _accepted_delivery(email="expired@example.edu", message_id="expired-message")
    conn = db.connect()
    try:
        conn.execute(
            "UPDATE ses_feedback_correlations SET feedback_expires_at=? WHERE provider_message_id=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), "expired-message"),
        )
        conn.commit()
    finally:
        conn.close()
    assert ses_feedback.process_ses_feedback(_sns_message(message_id="expired-message", sns_id="sns-expired")) == "ignored_unknown"
    conn = db.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM ses_recipient_suppressions").fetchone()[0] == 0
        assert conn.execute("SELECT status FROM professor_invitations WHERE id='inv-feedback'").fetchone()[0] == "active"
    finally:
        conn.close()


def test_suppressed_recipient_cannot_reserve_another_ses_send():
    _accepted_delivery()
    recipient_hash = recipient_suppression_hash("professor@example.edu")
    now = datetime.now(timezone.utc).isoformat()
    conn = db.connect()
    try:
        conn.execute("INSERT INTO ses_recipient_suppressions VALUES (?, 'complaint', ?, ?, 1)", (recipient_hash, now, now))
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(AdminError) as raised:
        InvitationRepository().reserve_email_delivery(
            invitation_id="inv-feedback", intended_email="professor@example.edu",
            secret="one-time-secret", owner_id="owner", idempotency_key="new-key",
            request_fingerprint="new-fingerprint", now=datetime.now(timezone.utc),
        )
    assert raised.value.code == "ADMIN_EMAIL_RECIPIENT_SUPPRESSED"


def test_sns_signature_topic_and_certificate_host_are_verified(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sns.us-east-1.amazonaws.com")])
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(private_key.public_key()).serial_number(1)
        .not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc)+timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    payload = {
        "Type": "Notification", "MessageId": "sns-signed", "TopicArn": TOPIC,
        "Message": json.dumps({"notificationType":"Bounce","mail":{"messageId":"m"},"bounce":{"bounceType":"Permanent"}}),
        "Timestamp": "2026-08-03T18:00:00.000Z", "SignatureVersion": "1",
        "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-test.pem",
    }
    payload["Signature"] = base64.b64encode(private_key.sign(ses_feedback._canonical_message(payload), padding.PKCS1v15(), hashes.SHA1())).decode()
    monkeypatch.setattr(ses_feedback, "_fetch_signing_certificate", lambda *_: cert_pem)
    assert ses_feedback.verify_sns_message(payload) == (TOPIC, "us-east-1")
    _accepted_delivery(message_id="m")
    ses_feedback.handle_sns_payload(payload, "Notification")
    conn = db.connect()
    try:
        assert tuple(conn.execute("SELECT reason FROM ses_recipient_suppressions").fetchone()) == ("permanent_bounce",)
    finally:
        conn.close()
    payload["TopicArn"] = "arn:aws:sns:us-east-1:123456789012:wrong"
    with pytest.raises(ValueError, match="unexpected SNS topic"):
        ses_feedback.verify_sns_message(payload)
    with pytest.raises(ValueError, match="untrusted SNS URL"):
        ses_feedback._validate_sns_url("https://evil.example/cert.pem", "us-east-1", certificate=True)


def test_route_requires_verified_payload_and_handles_subscription(monkeypatch):
    app = FastAPI()
    app.include_router(ses_feedback.router)
    client = TestClient(app)
    assert client.post("/api/email/ses-feedback", content=b"{}").status_code == 400
    called = []
    monkeypatch.setattr(ses_feedback, "verify_sns_message", lambda _payload: (TOPIC, "us-east-1"))
    monkeypatch.setattr(ses_feedback, "_confirm_subscription", lambda payload, region: called.append((payload["Token"], region)))
    payload = {"Type":"SubscriptionConfirmation","MessageId":"sns-sub","Message":"confirm","Timestamp":"2026-08-03T18:00:00Z","TopicArn":TOPIC,"Token":"token","SubscribeURL":"https://sns.us-east-1.amazonaws.com/?Action=ConfirmSubscription"}
    response = client.post("/api/email/ses-feedback", json=payload, headers={"x-amz-sns-message-type":"SubscriptionConfirmation"})
    assert response.status_code == 204
    assert called == [("token", "us-east-1")]
