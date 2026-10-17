from supportgenie.config import settings
from supportgenie.db.repository import InMemoryTicketRepository, TicketRepository, SqlServerTicketRepository


def get_ticket_repository() -> TicketRepository:
    if settings.demo_mode:
        return InMemoryTicketRepository()
    return SqlServerTicketRepository()
