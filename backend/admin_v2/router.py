"""Single mount point for the Admin Console V2 API."""

from fastapi import APIRouter

from .audit_exports_routes import router as audit_exports_router
from .audit_routes import router as audit_router
from .backups_routes import router as backups_router
from .cleanup_routes import router as cleanup_router
from .health_routes import router as health_router
from .invitations_routes import router as invitations_router
from .organizations_routes import router as organizations_router
from .routes import router as auth_router
from .sessions_routes import router as sessions_router
from .users_routes import router as users_router

router = APIRouter(prefix="/api/admin/v2")
router.include_router(auth_router)
router.include_router(organizations_router)
router.include_router(audit_router)
router.include_router(audit_exports_router)
router.include_router(invitations_router)
router.include_router(users_router)
router.include_router(sessions_router)
router.include_router(health_router)
router.include_router(backups_router)
router.include_router(cleanup_router)
