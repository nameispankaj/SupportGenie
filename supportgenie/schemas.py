from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class IssueCategory(str, Enum):
    PRODUCT_BUG = "Product Bug"
    DATA_ISSUE = "Data Issue"
    CONFIGURATION_ISSUE = "Configuration Issue"
    PERMISSION_ISSUE = "Permission Issue"
    INTEGRATION_ISSUE = "Integration Issue"
    EXPECTED_BEHAVIOUR = "Expected Behaviour"
    CHANGE_REQUEST = "Change Request"
    INSUFFICIENT_INFORMATION = "Insufficient Information"


class HandlingLevel(str, Enum):
    L1 = "L1 Support"
    L2 = "L2 Support"
    BUG_OR_PBI = "Bug/PBI"


class HealthResponse(BaseModel):
    status: str
    mode: str


class DashboardResponse(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    closed_tickets: int
    tickets_by_urgency: dict[str, int]
    tickets_by_category: dict[str, int]


class TicketListItem(BaseModel):
    ticket_id: str
    subject: str
    client: str | None = None
    project: str | None = None
    module: str | None = None
    status: str | None = None
    urgency: str | None = None
    assigned_support_associate: str | None = None
    report_date: datetime | None = None


class TicketListResponse(BaseModel):
    page: int
    page_size: int
    total_count: int
    items: list[TicketListItem]


class TicketHistoryItem(BaseModel):
    source: str
    message: str
    created_at: datetime | None = None
    author: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class TicketDetailResponse(BaseModel):
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


class TicketHistoryResponse(BaseModel):
    ticket_id: str
    history: list[TicketHistoryItem]


class AnalyzeTicketResponse(BaseModel):
    ticket_id: str
    ticket_subject: str
    ticket_description: str
    ticket_category: IssueCategory
    category_confidence: float
    classification_explanation: str
    suspected_root_cause: str
    possible_resolution: str
    evidence: list[str]
    unverified_hypotheses: list[str]
    missing_information: list[str]
    clarifying_questions: list[str]
    troubleshooting_steps: list[str]
    handling_level: HandlingLevel
    escalation_reason: str | None = None
    suggested_next_action: str


class RecordNoteRequest(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


class TicketFilterParams(BaseModel):
    ticket_id: str | None = None
    subject: str | None = None
    client: str | None = None
    project: str | None = None
    module: str | None = None
    status: str | None = None
    urgency: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
