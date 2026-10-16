from enum import Enum
from pydantic import BaseModel, Field, model_validator


class IssueCategory(str, Enum):
    PRODUCT_BUG = "Product Bug"
    DATA_ISSUE = "Data Issue"
    CONFIGURATION_ISSUE = "Configuration Issue"
    PERMISSION_ISSUE = "Permission Issue"
    INTEGRATION_ISSUE = "Integration Issue"
    EXPECTED_BEHAVIOUR = "Expected Behaviour"
    CHANGE_REQUEST = "Change Request"
    INSUFFICIENT_INFORMATION = "Insufficient Information"


class ResolutionPath(str, Enum):
    L1 = "L1_CAN_RESOLVE"
    L2 = "L2_INVESTIGATION_REQUIRED"
    BUG_OR_PBI = "PREPARE_BUG_OR_PBI_FOR_REVIEW"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TicketAnalysisRequest(BaseModel):
    ticket_id: str | None = Field(default=None, min_length=1)
    issue_description: str | None = Field(default=None, min_length=3)
    include_history: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_source(self) -> "TicketAnalysisRequest":
        if not self.ticket_id and not self.issue_description:
            raise ValueError("Provide ticket_id or issue_description.")
        return self


class AnalyzedTicketContext(BaseModel):
    ticket_id: str | None = None
    tenant_id: str
    issue_summary: str
    module: str | None = None
    project: str | None = None
    client: str | None = None


class TicketAnalysisResponse(BaseModel):
    context: AnalyzedTicketContext
    category: IssueCategory
    likely_root_cause: str
    possible_resolution: str
    verified_evidence: list[str]
    hypotheses: list[str]
    confidence: ConfidenceLevel
    missing_information: list[str]
    clarifying_questions: list[str]
    recommendation: ResolutionPath
    related_knowledge: list[str]
    demo_mode: bool
