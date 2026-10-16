from supportgenie.config import settings
from supportgenie.db.models import TicketRecord
from supportgenie.schemas import (
    AnalyzedTicketContext,
    IssueCategory,
    TicketAnalysisResponse,
)
from supportgenie.services.agent_orchestration import SupportAgentOrchestrator
from supportgenie.services.rag_service import RAGService


class TicketAnalysisService:
    def __init__(self) -> None:
        self.orchestrator = SupportAgentOrchestrator()
        self.rag = RAGService()

    def _missing_information(self, category: IssueCategory) -> list[str]:
        if category == IssueCategory.INSUFFICIENT_INFORMATION:
            return ["Reproduction steps", "Exact timestamp", "Error message or screenshot"]
        return []

    def _clarifying_questions(self, category: IssueCategory) -> list[str]:
        if category == IssueCategory.INSUFFICIENT_INFORMATION:
            return [
                "What exact action triggers the issue?",
                "When did this start and does it affect all users?",
                "Can you share logs, screenshots, or full error text?",
            ]
        return []

    def analyze(self, tenant_id: str, issue_summary: str, ticket: TicketRecord | None = None) -> TicketAnalysisResponse:
        category = IssueCategory(ticket.category) if ticket else self.orchestrator.classify_category(issue_summary)
        confidence = self.orchestrator.confidence_for(category, issue_summary)
        recommendation = self.orchestrator.recommendation_for(category)

        verified_evidence = []
        if ticket:
            verified_evidence.append(f"Ticket {ticket.ticket_id} exists for tenant {ticket.tenant_id}.")
            verified_evidence.extend([f"History: {entry}" for entry in ticket.history])

        hypotheses = [
            "Root-cause assessment is AI-assisted and should be validated by support engineer.",
            "Resolution recommendation may change if new logs or reproduction steps are provided.",
        ]

        return TicketAnalysisResponse(
            context=AnalyzedTicketContext(
                ticket_id=ticket.ticket_id if ticket else None,
                tenant_id=tenant_id,
                issue_summary=issue_summary,
                module=ticket.module if ticket else None,
                project=ticket.project if ticket else None,
                client=ticket.client if ticket else None,
            ),
            category=category,
            likely_root_cause=f"Likely {category.value.lower()} based on available ticket details.",
            possible_resolution="Follow the linked troubleshooting procedure, validate fix in non-production, and document outcome.",
            verified_evidence=verified_evidence,
            hypotheses=hypotheses,
            confidence=confidence,
            missing_information=self._missing_information(category),
            clarifying_questions=self._clarifying_questions(category),
            recommendation=recommendation,
            related_knowledge=self.rag.search(category, issue_summary),
            demo_mode=settings.demo_mode,
        )
