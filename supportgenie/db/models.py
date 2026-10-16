from pydantic import BaseModel


class TicketRecord(BaseModel):
    ticket_id: str
    tenant_id: str
    authorized_users: list[str]
    issue_description: str
    history: list[str]
    module: str | None = None
    project: str | None = None
    client: str | None = None
    category: str
