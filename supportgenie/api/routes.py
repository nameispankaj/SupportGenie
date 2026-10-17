from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from supportgenie.config import settings
from supportgenie.db.factory import get_ticket_repository
from supportgenie.db.models import TicketHistoryRecord
from supportgenie.db.repository import RepositoryError, SchemaUnavailableError, TicketNotFoundError
from supportgenie.schemas import (
    AnalyzeTicketResponse,
    DashboardResponse,
    HealthResponse,
    RecordNoteRequest,
    TicketDetailResponse,
    TicketFilterParams,
    TicketHistoryItem,
    TicketHistoryResponse,
    TicketListItem,
    TicketListResponse,
)
from supportgenie.services.analysis_service import TicketAnalysisService

router = APIRouter()
analysis_service = TicketAnalysisService()
_runtime_notes: dict[str, list[TicketHistoryRecord]] = {}


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    repository = get_ticket_repository()
    try:
        repository.health()
    except RepositoryError:
        return HealthResponse(status="degraded", mode="demo" if settings.demo_mode else "live")
    return HealthResponse(status="ok", mode="demo" if settings.demo_mode else "live")


@router.get("/api/dashboard", response_model=DashboardResponse)
def dashboard() -> DashboardResponse:
    repository = get_ticket_repository()
    try:
        return repository.dashboard()
    except SchemaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail="Unable to fetch dashboard data") from exc


@router.get("/api/tickets", response_model=TicketListResponse)
def list_tickets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="report_date"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    ticket_id: str | None = None,
    subject: str | None = None,
    client: str | None = None,
    project: str | None = None,
    module: str | None = None,
    status: str | None = None,
    urgency: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> TicketListResponse:
    repository = get_ticket_repository()
    try:
        filters = TicketFilterParams(
            ticket_id=ticket_id,
            subject=subject,
            client=client,
            project=project,
            module=module,
            status=status,
            urgency=urgency,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid filter parameters") from exc

    try:
        total_count, tickets = repository.list_tickets(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filters=filters,
        )
    except SchemaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TicketListResponse(
        page=page,
        page_size=page_size,
        total_count=total_count,
        items=[TicketListItem.model_validate(ticket.model_dump()) for ticket in tickets],
    )


@router.get("/api/tickets/{ticket_id}", response_model=TicketDetailResponse)
def get_ticket(ticket_id: str) -> TicketDetailResponse:
    repository = get_ticket_repository()
    try:
        ticket = repository.get_ticket(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SchemaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail="Unable to fetch ticket") from exc

    return TicketDetailResponse.model_validate(ticket.model_dump())


@router.get("/api/tickets/{ticket_id}/history", response_model=TicketHistoryResponse)
def get_ticket_history(ticket_id: str) -> TicketHistoryResponse:
    repository = get_ticket_repository()
    try:
        history = repository.get_ticket_history(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SchemaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail="Unable to fetch ticket history") from exc

    history.extend(_runtime_notes.get(ticket_id, []))
    return TicketHistoryResponse(
        ticket_id=ticket_id,
        history=[TicketHistoryItem.model_validate(item.model_dump()) for item in history],
    )


@router.post("/api/tickets/{ticket_id}/analyze", response_model=AnalyzeTicketResponse)
def analyze_ticket(ticket_id: str) -> AnalyzeTicketResponse:
    repository = get_ticket_repository()
    try:
        ticket = repository.get_ticket(ticket_id)
        history = repository.get_ticket_history(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SchemaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail="Unable to analyze ticket") from exc

    history.extend(_runtime_notes.get(ticket_id, []))
    return analysis_service.analyze(ticket=ticket, history=history)


@router.post("/api/tickets/{ticket_id}/notes", response_model=TicketHistoryItem, status_code=201)
def record_note(ticket_id: str, request: RecordNoteRequest) -> TicketHistoryItem:
    repository = get_ticket_repository()
    try:
        repository.get_ticket(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail="Unable to record note") from exc

    note = TicketHistoryRecord(
        ticket_id=ticket_id,
        source="TicketFollowups",
        message=request.note,
        author="support-associate",
    )
    _runtime_notes.setdefault(ticket_id, []).append(note)
    return TicketHistoryItem.model_validate(note.model_dump())
