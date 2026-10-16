from fastapi import APIRouter, Header, HTTPException

from supportgenie.db.factory import get_ticket_repository
from supportgenie.db.repository import AccessDeniedError
from supportgenie.schemas import TicketAnalysisRequest, TicketAnalysisResponse
from supportgenie.services.analysis_service import TicketAnalysisService

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ticket-analysis", response_model=TicketAnalysisResponse)
def analyze_ticket(
    request: TicketAnalysisRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    x_user_id: str = Header(..., alias="X-User-Id"),
) -> TicketAnalysisResponse:
    service = TicketAnalysisService()
    ticket = None

    if request.ticket_id:
        repository = get_ticket_repository()
        try:
            ticket = repository.get_ticket_by_id(ticket_id=request.ticket_id, tenant_id=x_tenant_id, user_id=x_user_id)
        except AccessDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

    issue_summary = ticket.issue_description if ticket else request.issue_description
    if not issue_summary:
        raise HTTPException(status_code=400, detail="Issue description is required when ticket not provided")

    return service.analyze(tenant_id=x_tenant_id, issue_summary=issue_summary, ticket=ticket)
