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


def _delivery_error(exc: Exception) -> AdminError:
    """Classify SES failures without exposing provider error text or recipient data."""
    from botocore.exceptions import BotoCoreError, ClientError

    if isinstance(exc, ClientError):
        provider_code = str(exc.response.get("Error", {}).get("Code") or "")
        code, message = {
            "MessageRejected": (
                "ADMIN_EMAIL_SES_MESSAGE_REJECTED",
                "SES rejected the invitation email",
            ),
            "AccessDenied": (
                "ADMIN_EMAIL_SES_ACCESS_DENIED",
                "SES denied permission to send the invitation email",
            ),
            "AccessDeniedException": (
                "ADMIN_EMAIL_SES_ACCESS_DENIED",
                "SES denied permission to send the invitation email",
            ),
            "Throttling": (
                "ADMIN_EMAIL_SES_THROTTLED",
                "SES temporarily throttled invitation email delivery",
            ),
            "ThrottlingException": (
                "ADMIN_EMAIL_SES_THROTTLED",
                "SES temporarily throttled invitation email delivery",
            ),
        }.get(
            provider_code,
            ("ADMIN_EMAIL_SES_CLIENT_ERROR", "SES could not accept the invitation email"),
        )
        return AdminError(503, code, message)
    if isinstance(exc, BotoCoreError):
        return AdminError(503, "ADMIN_EMAIL_SES_UNAVAILABLE", "SES is temporarily unavailable")
    return AdminError(503, "ADMIN_EMAIL_DELIVERY_FAILED", "SES could not accept the invitation email")


def _settings() -> tuple[str, str, str, str, str]:
    provider = os.environ.get("PRACTENTURE_EMAIL_PROVIDER", "").strip().casefold()
    sender = os.environ.get("PRACTENTURE_SES_SENDER", "").strip()
    region = os.environ.get("PRACTENTURE_SES_REGION", "us-east-1").strip()
    configuration_set = os.environ.get("PRACTENTURE_SES_CONFIGURATION_SET", "").strip()
    public_origin = os.environ.get("PRACTENTURE_PUBLIC_ORIGIN", "https://practenture.com").strip().rstrip("/")
    if provider != "ses" or not sender or not region or not public_origin.startswith("https://"):
        raise AdminError(503, "ADMIN_EMAIL_NOT_CONFIGURED", "Email delivery is not configured")
    return provider, sender, region, configuration_set, public_origin


def send_professor_invitation(*, recipient: str, secret: str) -> EmailDeliveryReceipt:
    """Send one code through SES using the EC2 instance role credential chain."""
    _, sender, region, configuration_set, public_origin = _settings()
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
        send_kwargs = {
            "Source": sender,
            "Destination": {"ToAddresses": [recipient]},
            "Message": {
                "Subject": {"Data": "Your Practenture professor invitation", "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        }
        if configuration_set:
            send_kwargs["ConfigurationSetName"] = configuration_set
        response = boto3.client("ses", region_name=region).send_email(**send_kwargs)
        message_id = str(response["MessageId"])
        if not message_id:
            raise KeyError("MessageId")
    except (BotoCoreError, ClientError, KeyError, TypeError) as exc:
        raise _delivery_error(exc) from exc
    return EmailDeliveryReceipt(message_id=message_id)
