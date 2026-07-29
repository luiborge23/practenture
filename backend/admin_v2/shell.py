"""Backend-served browser shell for Admin Console V2."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)
_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "admin_v2.html"
_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


@router.get("/admin", response_class=HTMLResponse)
@router.get("/admin/", response_class=HTMLResponse)
@router.get("/admin-v2", response_class=HTMLResponse)
@router.get("/admin-v2/", response_class=HTMLResponse)
async def admin_v2_shell() -> HTMLResponse:
    return HTMLResponse(_TEMPLATE.read_text(encoding="utf-8"), headers=_SECURITY_HEADERS)
