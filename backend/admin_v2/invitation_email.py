"""Amazon SES delivery adapter for professor invitations.

Secrets are accepted only at send time and never persisted or logged.
"""
from __future__ import annotations

from dataclasses import dataclass
import os

from .errors import AdminError


@dataclass(frozen=True)
class EmailDeliveryReceipt:
    message_id: str


def _settings() -> tuple[str, str, str, str]:
    provider = os.environ.get("PRACTENTURE_EMAIL_PROVIDER", "").strip().casefold()
    sender = os.environ.get("PRACTENTURE_SES_SENDER", "").strip()
    region = os.environ.get("PRACTENTURE_SES_REGION", "us-east-1").strip()
    public_origin = os.environ.get("PRACTENTURE_PUBLIC_ORIGIN", "https://practenture.com").strip().rstrip("/")
    if provider != "ses" or not sender or not region or not public_origin.startswith("https://"):
        raise AdminError(503, "ADMIN_EMAIL_NOT_CONFIGURED", "Email delivery is not configured")
    return provider, sender, region, public_origin


def send_professor_invitation(*, recipient: str, secret: str) -> EmailDeliveryReceipt:
    """Send one code through SES using the EC2 instance role credential chain."""
    _, sender, region, public_origin = _settings()
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError as exc:  # pragma: no cover - requirements contract covers this
        raise AdminError(503, "ADMIN_EMAIL_UNAVAILABLE", "Email delivery is unavailable") from exc

    body = (
        "You have been invited to create your Practenture professor account.\n\n"
        f"Open {public_origin}/login or the Practenture iOS app and enter this one-time invitation code:\n\n"
        f"{secret}\n\n"
        f"Use this exact email during enrollment: {recipient}\n\n"
        "This code expires as shown by your Administrator and can be used once."
    )
    try:
        response = boto3.client("ses", region_name=region).send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": "Your Practenture professor invitation", "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
    except (BotoCoreError, ClientError, KeyError, TypeError) as exc:
        raise AdminError(503, "ADMIN_EMAIL_DELIVERY_FAILED", "SES could not accept the invitation email") from exc
    return EmailDeliveryReceipt(message_id=str(response["MessageId"]))
