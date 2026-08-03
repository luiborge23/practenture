"""Verified Amazon SNS receiver for SES bounce and complaint feedback."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
from threading import Lock
import time
from urllib.parse import urlparse
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from admin_v2.redaction import redact_secrets
from database import db
from ses_suppression import normalize_recipient, recipient_suppression_hash

router = APIRouter(prefix="/api/email", tags=["email-feedback"])
_MAX_BODY_BYTES = 256 * 1024
_CERT_CACHE_SECONDS = 3600
_CERT_PATH = re.compile(r"^/SimpleNotificationService-[A-Za-z0-9_-]+\.pem$")
_CERT_CACHE: dict[str, tuple[float, bytes]] = {}
_CERT_LOCK = Lock()


def _settings() -> tuple[str, str]:
    topic = os.environ.get("PRACTENTURE_SES_SNS_TOPIC_ARN", "").strip()
    region = os.environ.get("PRACTENTURE_SES_REGION", "us-east-1").strip()
    expected_prefix = f"arn:aws:sns:{region}:"
    if not topic.startswith(expected_prefix) or topic.count(":") != 5:
        raise RuntimeError("SES SNS feedback topic is not configured for the SES region")
    recipient_suppression_hash("configuration-check@example.invalid", required=True)
    return topic, region


def _validate_sns_url(url: str, region: str, *, certificate: bool) -> str:
    parsed = urlparse(url)
    expected_host = f"sns.{region}.amazonaws.com"
    if (
        parsed.scheme != "https"
        or parsed.hostname != expected_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.fragment
    ):
        raise ValueError("untrusted SNS URL")
    if certificate and (parsed.query or not _CERT_PATH.fullmatch(parsed.path)):
        raise ValueError("untrusted SNS certificate URL")
    return url


def _fetch_signing_certificate(url: str, region: str) -> bytes:
    import httpx

    trusted = _validate_sns_url(url, region, certificate=True)
    now = time.monotonic()
    with _CERT_LOCK:
        cached = _CERT_CACHE.get(trusted)
        if cached and now - cached[0] < _CERT_CACHE_SECONDS:
            return cached[1]
    response = httpx.get(trusted, timeout=5.0, follow_redirects=False)
    response.raise_for_status()
    content = response.content
    if len(content) > 64 * 1024:
        raise ValueError("SNS certificate is too large")
    x509.load_pem_x509_certificate(content)
    with _CERT_LOCK:
        _CERT_CACHE[trusted] = (now, content)
    return content


def _canonical_message(payload: dict) -> bytes:
    message_type = payload.get("Type")
    fields = {
        "Notification": ("Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type"),
        "SubscriptionConfirmation": ("Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type"),
        "UnsubscribeConfirmation": ("Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type"),
    }.get(message_type)
    if fields is None:
        raise ValueError("unsupported SNS message type")
    parts: list[str] = []
    for field in fields:
        if field == "Subject" and field not in payload:
            continue
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError("invalid SNS message")
        parts.extend((field, value))
    return ("\n".join(parts) + "\n").encode("utf-8")


def verify_sns_message(payload: dict) -> tuple[str, str]:
    topic, region = _settings()
    candidate_topic = payload.get("TopicArn")
    if not isinstance(candidate_topic, str) or not hmac.compare_digest(candidate_topic, topic):
        raise ValueError("unexpected SNS topic")
    version = payload.get("SignatureVersion")
    if version not in ("1", "2"):
        raise ValueError("unsupported SNS signature version")
    signature_text = payload.get("Signature")
    cert_url = payload.get("SigningCertURL")
    if not isinstance(signature_text, str) or not isinstance(cert_url, str):
        raise ValueError("incomplete SNS signature")
    import base64
    try:
        signature = base64.b64decode(signature_text, validate=True)
    except ValueError as exc:
        raise ValueError("invalid SNS signature encoding") from exc
    certificate = x509.load_pem_x509_certificate(_fetch_signing_certificate(cert_url, region))
    now = datetime.now(timezone.utc)
    if now < certificate.not_valid_before_utc or now > certificate.not_valid_after_utc:
        raise ValueError("SNS signing certificate is not currently valid")
    digest = hashes.SHA1() if version == "1" else hashes.SHA256()
    certificate.public_key().verify(signature, _canonical_message(payload), padding.PKCS1v15(), digest)
    return topic, region


def _confirm_subscription(payload: dict, region: str) -> None:
    import httpx
    url = payload.get("SubscribeURL")
    if not isinstance(url, str):
        raise ValueError("missing SNS subscription URL")
    trusted = _validate_sns_url(url, region, certificate=False)
    response = httpx.get(trusted, timeout=5.0, follow_redirects=False)
    response.raise_for_status()


def process_ses_feedback(payload: dict) -> str:
    sns_message_id = str(payload["MessageId"])
    try:
        message = json.loads(str(payload["Message"]))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("invalid SES feedback message") from exc
    feedback_type = str(message.get("notificationType") or message.get("eventType") or "unknown").casefold()
    mail = message.get("mail")
    provider_message_id = str(mail.get("messageId") or "") if isinstance(mail, dict) else ""
    suppress_reason: str | None = None
    outcome = "ignored_unknown"
    if feedback_type == "complaint":
        suppress_reason, outcome = "complaint", "suppressed"
    elif feedback_type == "bounce":
        bounce = message.get("bounce")
        bounce_type = str(bounce.get("bounceType") or "") if isinstance(bounce, dict) else ""
        if bounce_type.casefold() == "permanent":
            suppress_reason, outcome = "permanent_bounce", "suppressed"
        else:
            outcome = "ignored_transient"

    now = datetime.now(timezone.utc).isoformat()
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT outcome FROM ses_feedback_events WHERE sns_message_id=?", (sns_message_id,)
        ).fetchone()
        if existing is not None:
            conn.commit()
            return str(existing[0])
        delivery = None
        if provider_message_id:
            delivery = conn.execute(
                """SELECT invitation_id, recipient_email FROM invitation_email_deliveries
                   WHERE provider='ses' AND state='accepted' AND provider_message_id=?
                   ORDER BY created_at DESC LIMIT 1""",
                (provider_message_id,),
            ).fetchone()
        if suppress_reason and delivery is not None:
            recipient_email = str(delivery[1])
            recipient_hash = recipient_suppression_hash(recipient_email, required=True)
            assert recipient_hash is not None
            conn.execute(
                """INSERT INTO ses_recipient_suppressions
                       (recipient_hash, reason, first_observed_at, last_observed_at, active)
                   VALUES (?, ?, ?, ?, 1)
                   ON CONFLICT(recipient_hash) DO UPDATE SET
                       reason=excluded.reason, last_observed_at=excluded.last_observed_at, active=1""",
                (recipient_hash, suppress_reason, now, now),
            )
            normalized = normalize_recipient(recipient_email)
            result = conn.execute(
                """UPDATE professor_invitations
                   SET status='revoked', revoked_at=?, revoked_by='ses-feedback'
                   WHERE lower(trim(intended_email))=? AND lower(status)='active'""",
                (now, normalized),
            )
            metadata = redact_secrets({
                "feedbackType": suppress_reason,
                "providerMessageIdHash": hashlib.sha256(provider_message_id.encode("utf-8")).hexdigest(),
                "recipientHashPrefix": recipient_hash[:12],
                "revokedCount": result.rowcount,
            })
            conn.execute(
                """INSERT INTO admin_audit_events
                       (id, request_id, actor_json, target_json, action, outcome, metadata_json, occurred_at)
                   VALUES (?, ?, ?, ?, 'invitation.email_feedback', 'succeeded', ?, ?)""",
                (
                    f"audit_{uuid4()}", f"sns_{sns_message_id}",
                    json.dumps({"id": "amazon-ses", "role": "system"}, separators=(",", ":")),
                    json.dumps({"type": "invitation", "id": str(delivery[0])}, separators=(",", ":")),
                    json.dumps(metadata, separators=(",", ":"), sort_keys=True), now,
                ),
            )
        elif suppress_reason:
            outcome = "ignored_unknown"
        conn.execute(
            """INSERT INTO ses_feedback_events
                   (sns_message_id, feedback_type, provider_message_id, outcome, occurred_at)
               VALUES (?, ?, ?, ?, ?)""",
            (sns_message_id, feedback_type, provider_message_id or None, outcome, now),
        )
        conn.commit()
        return outcome
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def handle_sns_payload(payload: dict, header_type: str | None) -> None:
    _, region = verify_sns_message(payload)
    message_type = str(payload.get("Type") or "")
    if header_type and not hmac.compare_digest(header_type, message_type):
        raise ValueError("SNS message type mismatch")
    if message_type == "SubscriptionConfirmation":
        _confirm_subscription(payload, region)
    elif message_type == "Notification":
        process_ses_feedback(payload)


@router.post("/ses-feedback", status_code=204, include_in_schema=False)
async def receive_ses_feedback(request: Request) -> Response:
    raw = await request.body()
    if not raw or len(raw) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=400, detail="Invalid SNS notification")
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("invalid payload")
        await run_in_threadpool(
            handle_sns_payload, payload, request.headers.get("x-amz-sns-message-type")
        )
    except (KeyError, TypeError, ValueError, RuntimeError):
        raise HTTPException(status_code=400, detail="Invalid SNS notification") from None
    except Exception:
        raise HTTPException(status_code=503, detail="SES feedback processing unavailable") from None
    return Response(status_code=204)
