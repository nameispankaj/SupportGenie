from abc import ABC, abstractmethod

from supportgenie.data.synthetic_tickets import SYNTHETIC_TICKETS
from supportgenie.db.models import TicketRecord


class AccessDeniedError(Exception):
    pass


class TicketRepository(ABC):
    @abstractmethod
    def get_ticket_by_id(self, ticket_id: str, tenant_id: str, user_id: str) -> TicketRecord | None:
        raise NotImplementedError


class SyntheticTicketRepository(TicketRepository):
    def __init__(self) -> None:
        self._tickets = [TicketRecord.model_validate(item) for item in SYNTHETIC_TICKETS]

    def get_ticket_by_id(self, ticket_id: str, tenant_id: str, user_id: str) -> TicketRecord | None:
        for ticket in self._tickets:
            if ticket.ticket_id != ticket_id:
                continue
            if ticket.tenant_id != tenant_id:
                raise AccessDeniedError("Ticket tenant mismatch.")
            if user_id not in ticket.authorized_users:
                raise AccessDeniedError("User is not authorized for this ticket.")
            return ticket
        return None
