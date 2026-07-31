"""Typed camelCase contracts for Admin V2 authentication."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True, extra="forbid")


class LoginRequest(CamelModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=1024)
    mfa_code: str | None = Field(default=None, alias="mfaCode", max_length=64)


class AdminSession(CamelModel):
    user_id: str = Field(alias="userId")
    role: str
    csrf_token: str = Field(alias="csrfToken")
    created_at: datetime = Field(alias="createdAt")
    last_seen_at: datetime = Field(alias="lastSeenAt")
    idle_expires_at: datetime = Field(alias="idleExpiresAt")
    absolute_expires_at: datetime = Field(alias="absoluteExpiresAt")


class SessionResponse(CamelModel):
    session: AdminSession


class MfaChallengeVerifyRequest(CamelModel):
    challenge_token: str = Field(alias="challengeToken", min_length=20, max_length=512)
    mfa_code: str = Field(alias="mfaCode", min_length=6, max_length=64)


class MfaStatusResponse(CamelModel):
    enabled: bool
    recovery_codes_remaining: int = Field(alias="recoveryCodesRemaining", ge=0)


class MfaSetupRequest(CamelModel):
    password: str = Field(min_length=1, max_length=1024)


class MfaSetupResponse(CamelModel):
    secret: str
    otpauth_uri: str = Field(alias="otpauthUri")
    qr_code_data_uri: str = Field(alias="qrCodeDataUri")


class MfaCodeRequest(CamelModel):
    code: str = Field(min_length=6, max_length=64)


class MfaProtectedMutationRequest(CamelModel):
    password: str = Field(min_length=1, max_length=1024)
    code: str = Field(min_length=6, max_length=64)


class MfaRecoveryCodesResponse(CamelModel):
    status: Literal["enabled", "regenerated"]
    recovery_codes: list[str] = Field(alias="recoveryCodes")


class MfaDisableResponse(CamelModel):
    status: Literal["disabled"] = "disabled"


class ReauthenticateRequest(CamelModel):
    password: str = Field(min_length=1, max_length=1024)
    mfa_code: str | None = Field(default=None, alias="mfaCode", min_length=6, max_length=64)


class ReauthenticateResponse(CamelModel):
    status: Literal["reauthenticated"] = "reauthenticated"
    recent_auth_expires_at: datetime = Field(alias="recentAuthExpiresAt")


class PasswordChangeRequest(CamelModel):
    current_password: str = Field(alias="currentPassword", min_length=1, max_length=1024)
    new_password: str = Field(alias="newPassword", min_length=12, max_length=1024)


class PasswordChangeResponse(CamelModel):
    status: Literal["password_changed"] = "password_changed"
    session: AdminSession


class RecoveryStartRequest(CamelModel):
    identifier: str = Field(min_length=1, max_length=320)


class RecoveryStartResponse(CamelModel):
    status: Literal["accepted"] = "accepted"


class RecoveryCompleteRequest(CamelModel):
    recovery_token: str = Field(alias="recoveryToken", min_length=20, max_length=512)
    new_password: str = Field(alias="newPassword", min_length=12, max_length=1024)


class RecoveryCompleteResponse(CamelModel):
    status: Literal["password_reset"] = "password_reset"
