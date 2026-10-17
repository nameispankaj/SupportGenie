"""
Ticket service layer coordinating TicketRepository and NLPService.
Validates business rules, statuses, and inputs before calling the repository.
"""

from typing import Any, Dict, List, Optional

from supportgenie.config import get_settings
from supportgenie.repositories.ticket_repository import (
    CATEGORY_CODE_MAP,
    STATUS_CODE_MAP,
    URGENCY_CODE_MAP,
    TicketRepository,
)
from supportgenie.services.nlp_service import NLPService, nlp_service


class TicketValidationError(ValueError):
    """Raised when ticket request parameters fail validation."""


class TicketNotFoundError(LookupError):
    """Raised when a requested ticket ID does not exist in SQL Server."""


class TicketService:
    """Service layer for support ticket operations and NLP analysis."""

    def __init__(
        self,
        repository: Optional[TicketRepository] = None,
        nlp: Optional[NLPService] = None,
    ) -> None:
        self.repository = repository or TicketRepository()
        self.nlp = nlp or nlp_service

    def get_dashboard(
        self,
        associate_id: Optional[int] = None,
        associate_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return dashboard counts and filter reference metadata from SQL Server."""
        cfg = get_settings()
        eff_id = associate_id if associate_id is not None else cfg.default_associate_id
        eff_name = (associate_name or cfg.default_associate_name).strip()

        counts = self.repository.get_dashboard_counts(
            associate_id=eff_id,
            associate_name=eff_name,
        )
        metadata = self.repository.get_filter_metadata()
        return {
            "counts": counts,
            "filters": metadata,
        }

    def list_tickets(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_pic: Optional[str] = None,
        client_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve filtered tickets from SQL Server."""
        return self.repository.list_tickets(
            search=search,
            status=status,
            category=category,
            priority=priority,
            assigned_pic=assigned_pic,
            client_id=client_id,
        )

    def get_ticket_details(self, ticket_id: int) -> Dict[str, Any]:
        """Retrieve ticket details and history for a valid ticket_id."""
        if ticket_id <= 0:
            raise TicketValidationError("Ticket ID must be a positive integer.")

        ticket = self.repository.get_ticket_by_id(ticket_id)
        if not ticket:
            raise TicketNotFoundError(f"Ticket #{ticket_id} was not found in SQL Server.")

        history = self.repository.get_ticket_history(ticket_id)
        return {
            "ticket": ticket,
            "history": history,
        }

    def get_ticket_history(self, ticket_id: int) -> Dict[str, Any]:
        """Retrieve communication, follow-ups, and update audit logs for a valid ticket_id."""
        if ticket_id <= 0:
            raise TicketValidationError("Ticket ID must be a positive integer.")

        ticket = self.repository.get_ticket_by_id(ticket_id)
        if not ticket:
            raise TicketNotFoundError(f"Ticket #{ticket_id} was not found in SQL Server.")

        return self.repository.get_ticket_history(ticket_id)

    def analyze_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """Run rule-based NLP analysis on an existing ticket with historical context."""
        if ticket_id <= 0:
            raise TicketValidationError("Ticket ID must be a positive integer.")

        ticket = self.repository.get_ticket_by_id(ticket_id)
        if not ticket:
            raise TicketNotFoundError(f"Ticket #{ticket_id} was not found in SQL Server.")

        history = self.repository.get_ticket_history(ticket_id)
        historical_candidates = self.repository.get_historical_tickets_for_nlp(
            exclude_ticket_id=ticket_id
        )
        return self.nlp.analyze_ticket(
            ticket=ticket,
            historical_tickets=historical_candidates,
            ticket_history=history,
        )

    def add_comment(
        self,
        ticket_id: int,
        text: str,
        note_type: str = "followup",
        added_by: Optional[int] = None,
        added_by_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate and persist a follow-up note or chat message for a ticket."""
        if ticket_id <= 0:
            raise TicketValidationError("Ticket ID must be a positive integer.")
        if not text or not text.strip():
            raise TicketValidationError("Comment or note text cannot be empty.")
        if len(text.strip()) > 4000:
            raise TicketValidationError("Comment text cannot exceed 4,000 characters.")

        clean_type = (note_type or "followup").strip().lower()
        if clean_type not in {"followup", "chat"}:
            raise TicketValidationError("note_type must be either 'followup' or 'chat'.")

        ticket = self.repository.get_ticket_by_id(ticket_id)
        if not ticket:
            raise TicketNotFoundError(f"Ticket #{ticket_id} was not found in SQL Server.")

        cfg = get_settings()
        eff_by = added_by if added_by is not None else cfg.default_associate_id
        eff_name = (added_by_name or cfg.default_associate_name).strip()

        return self.repository.add_comment_or_note(
            ticket_id=ticket_id,
            text=text.strip(),
            note_type=clean_type,
            added_by=eff_by,
            added_by_name=eff_name,
        )

    def update_ticket_status_or_fields(
        self,
        ticket_id: int,
        status_name: Optional[str] = None,
        pic_id: Optional[int] = None,
        remark: Optional[str] = None,
        category_name: Optional[str] = None,
        priority_name: Optional[str] = None,
        hours_spent: Optional[float] = None,
        updated_by: Optional[int] = None,
        updated_by_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate and persist status, assignment, category, priority, or resolution remark updates."""
        if ticket_id <= 0:
            raise TicketValidationError("Ticket ID must be a positive integer.")

        if all(
            v is None
            for v in (status_name, pic_id, remark, category_name, priority_name)
        ):
            raise TicketValidationError(
                "At least one update field (status, pic_id, remark, category, or priority) must be supplied."
            )

        if status_name is not None:
            clean_status = status_name.strip()
            if clean_status not in STATUS_CODE_MAP:
                allowed = ", ".join(STATUS_CODE_MAP.keys())
                raise TicketValidationError(f"Invalid status '{clean_status}'. Allowed values: {allowed}.")

        if category_name is not None:
            clean_cat = category_name.strip()
            if clean_cat not in CATEGORY_CODE_MAP:
                allowed = ", ".join(CATEGORY_CODE_MAP.keys())
                raise TicketValidationError(f"Invalid category '{clean_cat}'. Allowed values: {allowed}.")

        if priority_name is not None:
            clean_prio = priority_name.strip()
            if clean_prio not in URGENCY_CODE_MAP:
                allowed = ", ".join(URGENCY_CODE_MAP.keys())
                raise TicketValidationError(f"Invalid priority '{clean_prio}'. Allowed values: {allowed}.")

        if remark is not None and len(remark.strip()) > 2000:
            raise TicketValidationError("Resolution remark cannot exceed 2,000 characters (dbo.Tickets.Remark limit).")

        ticket = self.repository.get_ticket_by_id(ticket_id)
        if not ticket:
            raise TicketNotFoundError(f"Ticket #{ticket_id} was not found in SQL Server.")

        cfg = get_settings()
        eff_by = updated_by if updated_by is not None else cfg.default_associate_id
        eff_name = (updated_by_name or cfg.default_associate_name).strip()

        try:
            updated_ticket = self.repository.update_ticket(
                ticket_id=ticket_id,
                status_name=status_name,
                pic_id=pic_id,
                remark=remark,
                category_name=category_name,
                priority_name=priority_name,
                hours_spent=hours_spent,
                updated_by=eff_by,
                updated_by_name=eff_name,
            )
        except ValueError as exc:
            raise TicketValidationError(str(exc)) from exc

        return updated_ticket
