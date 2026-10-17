"""
FastAPI routes for support dashboard, ticket listing, ticket details, history,
NLP analysis, comments/notes, and status/resolution updates.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from supportgenie.database import DatabaseConnectionError, DatabaseError
from supportgenie.services.ticket_service import (
    TicketNotFoundError,
    TicketService,
    TicketValidationError,
)

router = APIRouter(prefix="/api", tags=["Support Tickets"])
ticket_service = TicketService()


class AddCommentRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000, description="Internal follow-up note or chat message text")
    note_type: str = Field(
        default="followup",
        description="Target table: 'followup' (dbo.TicketFollowups) or 'chat' (dbo.TicketChat)",
    )
    added_by: Optional[int] = Field(default=None, description="Numeric associate ID")
    added_by_name: Optional[str] = Field(default=None, max_length=200, description="Associate display name")


class UpdateTicketStatusRequest(BaseModel):
    status: Optional[str] = Field(default=None, description="New TicketStatusName ('Open', 'In Progress', 'Closed')")
    pic_id: Optional[int] = Field(default=None, description="Assigned associate ID from dbo.Pic")
    remark: Optional[str] = Field(default=None, max_length=2000, description="Resolution or status remark (dbo.Tickets.Remark)")
    category: Optional[str] = Field(default=None, description="TicketTypeName classification")
    priority: Optional[str] = Field(default=None, description="TicketUrgencyName ('High', 'Medium', 'Low')")
    hours_spent: Optional[float] = Field(default=None, ge=0.0, description="HoursSpentToClose when closing a ticket")
    updated_by: Optional[int] = Field(default=None, description="Numeric associate ID performing update")
    updated_by_name: Optional[str] = Field(default=None, max_length=200, description="Associate display name")


def _handle_service_exception(exc: Exception) -> None:
    if isinstance(exc, TicketValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, TicketNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, DatabaseConnectionError):
        raise HTTPException(status_code=503, detail=exc.message) from exc
    if isinstance(exc, DatabaseError):
        raise HTTPException(status_code=500, detail=exc.message) from exc
    raise HTTPException(status_code=500, detail="An unexpected server error occurred.") from exc


@router.get("/dashboard")
def get_dashboard(
    associate_id: Optional[int] = Query(default=None, description="Active support associate ID from dbo.Pic"),
    associate_name: Optional[str] = Query(default=None, description="Active support associate name from dbo.Pic"),
) -> Dict[str, Any]:
    """Retrieve real ticket counts and filter reference metadata from SQL Server."""
    try:
        return ticket_service.get_dashboard(associate_id=associate_id, associate_name=associate_name)
    except Exception as exc:
        _handle_service_exception(exc)
        return {}


@router.get("/tickets")
def list_tickets(
    search: Optional[str] = Query(default=None, description="Search by ticket ID, subject, description, or client"),
    status: Optional[str] = Query(default=None, description="Filter by TicketStatusName"),
    category: Optional[str] = Query(default=None, description="Filter by TicketTypeName"),
    priority: Optional[str] = Query(default=None, description="Filter by TicketUrgencyName"),
    assigned_pic: Optional[str] = Query(default=None, description="Filter by assigned associate name or ID"),
    client_id: Optional[int] = Query(default=None, description="Filter by ClientId"),
) -> Dict[str, Any]:
    """Retrieve tickets from dbo.Tickets with optional filters."""
    try:
        items = ticket_service.list_tickets(
            search=search,
            status=status,
            category=category,
            priority=priority,
            assigned_pic=assigned_pic,
            client_id=client_id,
        )
        return {"count": len(items), "tickets": items}
    except Exception as exc:
        _handle_service_exception(exc)
        return {}


@router.get("/tickets/{ticket_id}")
def get_ticket_details(
    ticket_id: int = Path(..., description="Ticket primary key Id in dbo.Tickets"),
) -> Dict[str, Any]:
    """Retrieve full ticket details and history for a specific ticket."""
    try:
        return ticket_service.get_ticket_details(ticket_id=ticket_id)
    except Exception as exc:
        _handle_service_exception(exc)
        return {}


@router.get("/tickets/{ticket_id}/history")
def get_ticket_history(
    ticket_id: int = Path(..., description="Ticket primary key Id in dbo.Tickets"),
) -> Dict[str, Any]:
    """Retrieve chats, internal follow-up notes, linked email messages, and update audit logs."""
    try:
        return ticket_service.get_ticket_history(ticket_id=ticket_id)
    except Exception as exc:
        _handle_service_exception(exc)
        return {}


@router.post("/tickets/{ticket_id}/analyze")
def analyze_ticket(
    ticket_id: int = Path(..., description="Ticket primary key Id in dbo.Tickets"),
) -> Dict[str, Any]:
    """Run rule-based NLP classification, root-cause hypothesis, and resolution analysis on a ticket."""
    try:
        return ticket_service.analyze_ticket(ticket_id=ticket_id)
    except Exception as exc:
        _handle_service_exception(exc)
        return {}


@router.post("/tickets/{ticket_id}/comments", status_code=201)
def add_ticket_comment(
    payload: AddCommentRequest,
    ticket_id: int = Path(..., description="Ticket primary key Id in dbo.Tickets"),
) -> Dict[str, Any]:
    """Add an internal follow-up note (dbo.TicketFollowups) or chat message (dbo.TicketChat)."""
    try:
        created = ticket_service.add_comment(
            ticket_id=ticket_id,
            text=payload.text,
            note_type=payload.note_type,
            added_by=payload.added_by,
            added_by_name=payload.added_by_name,
        )
        return {
            "status": "success",
            "message": (
                "Internal follow-up note saved to dbo.TicketFollowups."
                if created["note_type"] == "followup"
                else "Chat message saved to dbo.TicketChat."
            ),
            "comment": created,
        }
    except Exception as exc:
        _handle_service_exception(exc)
        return {}


@router.patch("/tickets/{ticket_id}/status")
def update_ticket_status(
    payload: UpdateTicketStatusRequest,
    ticket_id: int = Path(..., description="Ticket primary key Id in dbo.Tickets"),
) -> Dict[str, Any]:
    """Update ticket status, assigned associate (PIC), category, priority, or resolution remark in SQL Server."""
    try:
        updated = ticket_service.update_ticket_status_or_fields(
            ticket_id=ticket_id,
            status_name=payload.status,
            pic_id=payload.pic_id,
            remark=payload.remark,
            category_name=payload.category,
            priority_name=payload.priority,
            hours_spent=payload.hours_spent,
            updated_by=payload.updated_by,
            updated_by_name=payload.updated_by_name,
        )
        return {
            "status": "success",
            "message": f"Ticket #{ticket_id} updated in SQL Server and logged in dbo.UpdateLogs.",
            "ticket": updated,
        }
    except Exception as exc:
        _handle_service_exception(exc)
        return {}
