"""
FastAPI routes for retrieving ticket-linked email records and sending support emails.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from supportgenie.database import DatabaseConnectionError, DatabaseError
from supportgenie.services.email_service import EmailService, EmailValidationError

router = APIRouter(prefix="/api/emails", tags=["Support Emails"])
email_service = EmailService()


class SendEmailRequest(BaseModel):
    to: str = Field(..., min_length=3, max_length=500, description="Recipient email address(es)")
    cc: Optional[str] = Field(default=None, max_length=1000, description="Optional CC email address(es)")
    bcc: Optional[str] = Field(default=None, max_length=1000, description="Optional BCC email address(es)")
    subject: str = Field(..., min_length=1, max_length=500, description="Email subject line")
    body: str = Field(..., min_length=1, max_length=20000, description="Plain-text email body")
    ticket_id: Optional[int] = Field(
        default=None,
        description="Optional existing TicketId to link outbound MessageId in dbo.TicketEmailMessages",
    )
    added_by: Optional[int] = Field(default=None, description="Sender associate ID")
    added_by_name: Optional[str] = Field(default=None, max_length=200, description="Sender associate name")


@router.get("")
def list_emails(
    folder: Optional[str] = Query(default="all", description="Filter by folder: 'inbox', 'sent', or 'all'"),
    search: Optional[str] = Query(default=None, description="Search across MessageId, Subject, FromEmail, ClientName"),
) -> Dict[str, Any]:
    """Retrieve email records from dbo.TicketEmailMessages joined with dbo.Tickets."""
    try:
        return email_service.get_email_records(folder=folder, search=search)
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc


@router.post("/send")
def send_email(payload: SendEmailRequest) -> Dict[str, Any]:
    """
    Validate and send an email via SMTP when configured in .env.
    Never simulates delivery; returns explicit status flags for 'sent' and 'recorded_in_db'.
    """
    try:
        result = email_service.send_email(
            to_email=payload.to,
            subject=payload.subject,
            body=payload.body,
            cc_email=payload.cc,
            bcc_email=payload.bcc,
            ticket_id=payload.ticket_id,
            added_by=payload.added_by,
            added_by_name=payload.added_by_name,
        )
        return result
    except EmailValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc
