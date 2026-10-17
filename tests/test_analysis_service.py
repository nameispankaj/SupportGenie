from supportgenie.db.models import TicketHistoryRecord, TicketRecord
from supportgenie.schemas import IssueCategory
from supportgenie.services.analysis_service import TicketAnalysisService

service = TicketAnalysisService()


def make_ticket(subject: str, description: str) -> TicketRecord:
    return TicketRecord(ticket_id="X", subject=subject, description=description)


def analyze(subject: str, description: str, history: list[str] | None = None):
    history_items = [TicketHistoryRecord(ticket_id="X", source="TicketChat", message=item) for item in (history or [])]
    return service.analyze(make_ticket(subject, description), history_items)


def test_all_categories_supported() -> None:
    assert analyze("Crash on save", "Stack trace and exception in logs").ticket_category == IssueCategory.PRODUCT_BUG
    assert analyze("Wrong totals", "Duplicate data rows and mismatch").ticket_category == IssueCategory.DATA_ISSUE
    assert analyze("Email not sending", "SMTP configuration invalid").ticket_category == IssueCategory.CONFIGURATION_ISSUE
    assert analyze("Cannot access", "Access denied for role").ticket_category == IssueCategory.PERMISSION_ISSUE
    assert analyze("Sync failing", "Integration API timeout and token failure").ticket_category == IssueCategory.INTEGRATION_ISSUE
    assert analyze("Looks expected", "Behavior is by design and documented").ticket_category == IssueCategory.EXPECTED_BEHAVIOUR
    assert analyze("New export", "Request new feature for bulk export").ticket_category == IssueCategory.CHANGE_REQUEST
    assert analyze("Issue", "It does not work").ticket_category == IssueCategory.INSUFFICIENT_INFORMATION


def test_ambiguous_case_is_conservative() -> None:
    result = analyze("API permission problem", "Integration api returns unauthorized access denied")
    assert result.category_confidence <= 0.62
    assert result.unverified_hypotheses


def test_insufficient_information_case() -> None:
    result = analyze("Help", "Bad")
    assert result.ticket_category == IssueCategory.INSUFFICIENT_INFORMATION
    assert result.missing_information
    assert result.clarifying_questions


def test_conflicting_keywords_can_fall_back_to_insufficient() -> None:
    result = analyze("Crash or request?", "Need a new feature but also says bug maybe maybe")
    assert result.ticket_category in {IssueCategory.INSUFFICIENT_INFORMATION, IssueCategory.PRODUCT_BUG, IssueCategory.CHANGE_REQUEST}
    if result.ticket_category == IssueCategory.INSUFFICIENT_INFORMATION:
        assert result.category_confidence <= 0.3
