"""Standalone Admin V2 cleanup-plan routes."""
from fastapi import APIRouter, Depends, Header, Request, Response
from .cleanup_schemas import CleanupPlanCreateRequest, CleanupExecuteRequest, CleanupExecutionResponse, CleanupPlanResponse
from .cleanup_service import CleanupService
from .dependencies import require_admin_session, require_recent_auth_session
from .service import AuthenticatedSession

router=APIRouter(prefix="/operations",tags=["admin-v2-operations"])
_service=CleanupService()
def get_cleanup_service() -> CleanupService: return _service

@router.post("/cleanup-plans",response_model=CleanupPlanResponse,status_code=201)
def create_cleanup_plan(payload: CleanupPlanCreateRequest, session: AuthenticatedSession=Depends(require_admin_session), service: CleanupService=Depends(get_cleanup_service)):
    return service.create_plan(session=session,session_codes=payload.selector.session_codes)

@router.get("/cleanup-plans/{plan_id}",response_model=CleanupPlanResponse)
def get_cleanup_plan(plan_id: str, session: AuthenticatedSession=Depends(require_admin_session), service: CleanupService=Depends(get_cleanup_service)):
    del session
    return service.get_plan(plan_id)

@router.post("/cleanup-plans/{plan_id}/execute",response_model=CleanupExecutionResponse)
def execute_cleanup_plan(plan_id: str,payload: CleanupExecuteRequest,request: Request,response: Response,idempotency_key: str|None=Header(default=None,alias="Idempotency-Key"),session: AuthenticatedSession=Depends(require_recent_auth_session),service: CleanupService=Depends(get_cleanup_service)):
    execution=service.execute(session=session,plan_id=plan_id,plan_hash=payload.plan_hash,confirmation=payload.confirmation,idempotency_key=idempotency_key,request_id=request.state.request_id)
    for name,value in execution.response.headers.items(): response.headers[name]=value
    return execution.response.body
