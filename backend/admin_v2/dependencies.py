"""FastAPI dependencies for Admin V2 session and CSRF boundaries."""

from fastapi import Depends, Header, Request

from .service import AuthenticatedSession, COOKIE_NAME, auth_service


def require_admin_session(request: Request) -> AuthenticatedSession:
    session, _ = auth_service.authenticate(request.cookies.get(COOKIE_NAME))
    return session


def require_csrf_session(
    request: Request, x_csrf_token: str | None = Header(default=None)
) -> AuthenticatedSession:
    session, _ = auth_service.authenticate(request.cookies.get(COOKIE_NAME))
    auth_service.verify_csrf(session, x_csrf_token)
    return session


def require_recent_auth_session(
    session: AuthenticatedSession = Depends(require_csrf_session),
) -> AuthenticatedSession:
    """Require session + CSRF + a five-minute reauthentication grant."""
    auth_service.require_recent_auth(session)
    return session
