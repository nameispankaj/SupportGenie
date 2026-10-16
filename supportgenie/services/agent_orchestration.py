from supportgenie.schemas import (
    ConfidenceLevel,
    IssueCategory,
    ResolutionPath,
)


class SupportAgentOrchestrator:
    """Demo orchestration layer.

    Production integration should plug in Microsoft Agent Framework orchestration
    and Azure AI Foundry model calls.
    """

    def classify_category(self, text: str) -> IssueCategory:
        lowered = text.lower()
        if any(token in lowered for token in ["crash", "exception", "null reference", "bug"]):
            return IssueCategory.PRODUCT_BUG
        if any(token in lowered for token in ["duplicate rows", "incorrect data", "data table", "data mismatch"]):
            return IssueCategory.DATA_ISSUE
        if any(token in lowered for token in ["config", "configuration", "smtp", "environment variable", "settings"]):
            return IssueCategory.CONFIGURATION_ISSUE
        if any(token in lowered for token in ["access denied", "permission", "role", "unauthorized user"]):
            return IssueCategory.PERMISSION_ISSUE
        if any(token in lowered for token in ["api", "integration", "sync", "oauth", "token endpoint"]):
            return IssueCategory.INTEGRATION_ISSUE
        if any(token in lowered for token in ["by design", "expected", "documented behavior", "intended"]):
            return IssueCategory.EXPECTED_BEHAVIOUR
        if any(token in lowered for token in ["request", "enhancement", "new feature", "new button"]):
            return IssueCategory.CHANGE_REQUEST
        if len(text.strip()) < 20 or "does not work" in lowered:
            return IssueCategory.INSUFFICIENT_INFORMATION
        return IssueCategory.INSUFFICIENT_INFORMATION

    def confidence_for(self, category: IssueCategory, text: str) -> ConfidenceLevel:
        if category == IssueCategory.INSUFFICIENT_INFORMATION:
            return ConfidenceLevel.LOW
        if len(text) > 60:
            return ConfidenceLevel.HIGH
        return ConfidenceLevel.MEDIUM

    def recommendation_for(self, category: IssueCategory) -> ResolutionPath:
        if category in {IssueCategory.CONFIGURATION_ISSUE, IssueCategory.PERMISSION_ISSUE, IssueCategory.EXPECTED_BEHAVIOUR}:
            return ResolutionPath.L1
        if category in {IssueCategory.PRODUCT_BUG, IssueCategory.CHANGE_REQUEST}:
            return ResolutionPath.BUG_OR_PBI
        return ResolutionPath.L2
