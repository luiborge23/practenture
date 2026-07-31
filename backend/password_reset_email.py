"""SES delivery for one-time password-reset codes.

The raw reset code exists only in request memory and the email body. It is never
logged or persisted; the database stores only its SHA-256 hash.
"""
from __future__ import annotations

import os
from urllib.parse import quote


class PasswordResetDeliveryError(RuntimeError):
    """Raised when the configured provider cannot accept a reset email."""


def send_password_reset_code(*, recipient: str, code: str) -> str:
    provider = os.environ.get("PRACTENTURE_EMAIL_PROVIDER", "").strip().casefold()
    sender = os.environ.get("PRACTENTURE_SES_SENDER", "").strip()
    region = os.environ.get("PRACTENTURE_SES_REGION", "us-east-1").strip()
    origin = os.environ.get(
        "PRACTENTURE_PUBLIC_ORIGIN", "https://practenture.com"
    ).strip().rstrip("/")
    if provider != "ses" or not sender or not region or not origin.startswith("https://"):
        raise PasswordResetDeliveryError("Password-reset email is not configured")

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError as exc:  # pragma: no cover - deployment dependency contract
        raise PasswordResetDeliveryError("Password-reset email is unavailable") from exc

    body = (
        "A password reset was requested for your Practenture account.\n\n"
        f"Open {origin}/login, choose Forgot password, and enter this one-time reset code:\n\n"
        f"{code}\n\n"
        "This code expires in one hour and can be used once. If you did not request "
        "this reset, you can ignore this email."
    )
    try:
        response = boto3.client("ses", region_name=region).send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {
                    "Data": "Reset your Practenture password",
                    "Charset": "UTF-8",
                },
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        message_id = str(response["MessageId"])
        if not message_id:
            raise KeyError("MessageId")
    except (BotoCoreError, ClientError, KeyError, TypeError) as exc:
        raise PasswordResetDeliveryError(
            "SES could not accept the password-reset email"
        ) from exc
    return message_id


def send_admin_recovery_link(*, recipient: str, token: str) -> str:
    """Deliver a one-time Administrator recovery link through configured SES.

    The token is placed in the URL fragment so it is never included in the HTTP
    request, reverse-proxy logs, or server access logs. The Admin browser shell
    reads the fragment locally and submits the token only to the completion API.
    """
    provider = os.environ.get("PRACTENTURE_EMAIL_PROVIDER", "").strip().casefold()
    sender = os.environ.get("PRACTENTURE_SES_SENDER", "").strip()
    region = os.environ.get("PRACTENTURE_SES_REGION", "us-east-1").strip()
    origin = os.environ.get(
        "PRACTENTURE_PUBLIC_ORIGIN", "https://practenture.com"
    ).strip().rstrip("/")
    if provider != "ses" or not sender or not region or not origin.startswith("https://"):
        raise PasswordResetDeliveryError("Administrator recovery email is not configured")

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError as exc:  # pragma: no cover - deployment dependency contract
        raise PasswordResetDeliveryError("Administrator recovery email is unavailable") from exc

    recovery_url = f"{origin}/admin#recover={quote(token, safe='')}"
    body = (
        "A password reset was requested for your Practenture Administrator account.\n\n"
        f"Open this one-time recovery link:\n\n{recovery_url}\n\n"
        "The link expires in 30 minutes and can be used once. Completing recovery "
        "revokes every existing Administrator and API session. If you did not "
        "request this reset, you can ignore this email."
    )
    try:
        response = boto3.client("ses", region_name=region).send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {
                    "Data": "Recover your Practenture Administrator account",
                    "Charset": "UTF-8",
                },
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        message_id = str(response["MessageId"])
        if not message_id:
            raise KeyError("MessageId")
    except (BotoCoreError, ClientError, KeyError, TypeError) as exc:
        raise PasswordResetDeliveryError(
            "SES could not accept the Administrator recovery email"
        ) from exc
    return message_id
