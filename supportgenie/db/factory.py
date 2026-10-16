from supportgenie.config import settings
from supportgenie.db.repository import SyntheticTicketRepository, TicketRepository


def get_ticket_repository() -> TicketRepository:
    # Demo mode returns synthetic read-only repository.
    # SQL Server implementation can be injected later when authorized and configured.
    if settings.demo_mode:
        return SyntheticTicketRepository()
    return SyntheticTicketRepository()
