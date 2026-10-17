from datetime import datetime

from pydantic import BaseModel, Field


class TicketRecord(BaseModel):
    ticket_id: str
    subject: str
    description: str
    client: str | None = None
    project: str | None = None
    module: str | None = None
    status: str | None = None
    urgency: str | None = None
    assigned_support_associate: str | None = None
    report_date: datetime | None = None
    report_method: str | None = None


class TicketHistoryRecord(BaseModel):
    ticket_id: str
    source: str
    message: str
    created_at: datetime | None = None
    author: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class SchemaTable(BaseModel):
    table_name: str
    columns: list[str]
