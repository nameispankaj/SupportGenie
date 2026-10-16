from supportgenie.schemas import IssueCategory


class RAGService:
    def search(self, category: IssueCategory, issue_summary: str) -> list[str]:
        references: dict[IssueCategory, list[str]] = {
            IssueCategory.PRODUCT_BUG: ["Known issue playbook: collect stack trace and release version.", "Bug triage SOP: include reproducible steps and impact."],
            IssueCategory.DATA_ISSUE: ["Data correction runbook: validate source-of-truth and deduplicate records."],
            IssueCategory.CONFIGURATION_ISSUE: ["Configuration checklist: verify environment variables and service endpoints."],
            IssueCategory.PERMISSION_ISSUE: ["Access matrix guide: confirm user role assignment and scope."],
            IssueCategory.INTEGRATION_ISSUE: ["Integration troubleshooting: verify API credentials and token refresh flow."],
            IssueCategory.EXPECTED_BEHAVIOUR: ["Product behavior reference: compare expected outcome against documented design."],
            IssueCategory.CHANGE_REQUEST: ["Enhancement intake template: capture business value and acceptance criteria."],
            IssueCategory.INSUFFICIENT_INFORMATION: ["Information checklist: logs, timestamps, reproduction steps, and screenshots."],
        }
        return references.get(category, [])
