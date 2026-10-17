from __future__ import annotations

from dataclasses import dataclass
import re

from supportgenie.db.models import TicketHistoryRecord, TicketRecord
from supportgenie.schemas import AnalyzeTicketResponse, HandlingLevel, IssueCategory


@dataclass(frozen=True)
class CategoryProfile:
    category: IssueCategory
    keywords: tuple[str, ...]
    handling_level: HandlingLevel
    suspected_root_cause: str
    possible_resolution: str
    escalation_reason: str | None
    troubleshooting_steps: tuple[str, ...]
    next_action: str


class TicketAnalysisService:
    PROFILES: tuple[CategoryProfile, ...] = (
        CategoryProfile(
            category=IssueCategory.PRODUCT_BUG,
            keywords=("crash", "exception", "stack trace", "null reference", "bug", "error"),
            handling_level=HandlingLevel.BUG_OR_PBI,
            suspected_root_cause="A potential application defect introduced by recent code or dependency behavior.",
            possible_resolution="Capture reproduction steps and logs, then create or update a bug ticket for engineering triage.",
            escalation_reason="Strong defect indicators require product/development review.",
            troubleshooting_steps=(
                "Confirm reproducibility in a controlled environment.",
                "Collect stack trace, timestamp, and affected release version.",
                "Validate whether issue is tenant-specific or broad.",
            ),
            next_action="Prepare bug report with evidence and route to product/development.",
        ),
        CategoryProfile(
            category=IssueCategory.DATA_ISSUE,
            keywords=("missing", "incorrect", "duplicate", "mismatch", "data", "totals"),
            handling_level=HandlingLevel.L2,
            suspected_root_cause="Underlying records, filters, or transaction state may be inconsistent.",
            possible_resolution="Validate source records, tenant scope, status filters, and update history before correction.",
            escalation_reason=None,
            troubleshooting_steps=(
                "Verify record existence in authoritative data source.",
                "Check tenant, date, and status filters used by UI/report.",
                "Review transaction/update logs for anomalies.",
            ),
            next_action="Perform controlled data validation and document findings for L2 follow-up.",
        ),
        CategoryProfile(
            category=IssueCategory.CONFIGURATION_ISSUE,
            keywords=("config", "configuration", "setting", "smtp", "workflow", "environment"),
            handling_level=HandlingLevel.L1,
            suspected_root_cause="System settings may not match expected operational configuration.",
            possible_resolution="Compare current configuration to baseline and correct mismatched settings.",
            escalation_reason=None,
            troubleshooting_steps=(
                "Review relevant application and environment settings.",
                "Compare with known-good configuration baseline.",
                "Re-test scenario after configuration correction.",
            ),
            next_action="Validate and correct configuration using approved change process.",
        ),
        CategoryProfile(
            category=IssueCategory.PERMISSION_ISSUE,
            keywords=("access denied", "permission", "role", "forbidden", "unauthorized user"),
            handling_level=HandlingLevel.L1,
            suspected_root_cause="User role assignment or effective permission scope may be incorrect.",
            possible_resolution="Verify assigned role and effective permissions; adjust only through approved access controls.",
            escalation_reason=None,
            troubleshooting_steps=(
                "Check assigned role and group membership.",
                "Validate effective permissions for requested action.",
                "Confirm tenant and object-level access scope.",
            ),
            next_action="Run role and permission verification checklist before any access change.",
        ),
        CategoryProfile(
            category=IssueCategory.INTEGRATION_ISSUE,
            keywords=("api", "integration", "sync", "timeout", "token", "401", "webhook"),
            handling_level=HandlingLevel.L2,
            suspected_root_cause="External service communication, authentication, or reliability issue is likely.",
            possible_resolution="Inspect request/response traces, correlation IDs, token validity, and connectivity.",
            escalation_reason=None,
            troubleshooting_steps=(
                "Capture timestamp and correlation/request IDs.",
                "Validate API credentials/token lifecycle and endpoint reachability.",
                "Review integration logs for retries or upstream failures.",
            ),
            next_action="Collect integration diagnostics and continue L2 API/log investigation.",
        ),
        CategoryProfile(
            category=IssueCategory.EXPECTED_BEHAVIOUR,
            keywords=("expected", "by design", "documented", "intended", "works as designed"),
            handling_level=HandlingLevel.L1,
            suspected_root_cause="Observed behavior appears aligned with current product design/configuration.",
            possible_resolution="Share documented behavior and propose training or process guidance.",
            escalation_reason=None,
            troubleshooting_steps=(
                "Confirm behavior against product documentation.",
                "Validate no misconfiguration affects expected outcome.",
                "Communicate expected behavior with examples.",
            ),
            next_action="Provide documented clarification to reporter and confirm acceptance.",
        ),
        CategoryProfile(
            category=IssueCategory.CHANGE_REQUEST,
            keywords=("request", "enhancement", "new feature", "add", "improvement", "feature"),
            handling_level=HandlingLevel.BUG_OR_PBI,
            suspected_root_cause="Reporter is requesting new capability rather than defect correction.",
            possible_resolution="Capture business value and acceptance criteria for Product Backlog Item review.",
            escalation_reason="Change request should go through product backlog prioritization, not defect flow.",
            troubleshooting_steps=(
                "Clarify desired outcome and user impact.",
                "Capture acceptance criteria and success metrics.",
                "Route request through product prioritization.",
            ),
            next_action="Prepare enhancement/PBI proposal with scope and impact summary.",
        ),
    )

    def analyze(self, ticket: TicketRecord, history: list[TicketHistoryRecord]) -> AnalyzeTicketResponse:
        context_texts = [ticket.subject, ticket.description] + [item.message for item in history]
        scores = self._score(context_texts)
        best_profile, confidence = self._pick_profile(scores, context_texts)

        evidence = self._extract_evidence(best_profile, context_texts)
        if best_profile.category == IssueCategory.INSUFFICIENT_INFORMATION:
            missing_information = [
                "Exact reproduction steps",
                "Precise timestamp and impacted user scope",
                "Relevant logs, screenshots, or error text",
            ]
            clarifying_questions = [
                "What exact action triggers the issue?",
                "When did this start, and who is affected?",
                "Can you provide logs/screenshots/full error text?",
            ]
            unverified_hypotheses = [
                "Insufficient context to determine whether issue is defect, data, access, or configuration related."
            ]
            explanation = "Insufficient explicit evidence in ticket description and history to classify reliably."
            troubleshooting_steps = [
                "Collect missing evidence before categorization.",
                "Re-run analysis after clarification.",
            ]
            return AnalyzeTicketResponse(
                ticket_id=ticket.ticket_id,
                ticket_subject=ticket.subject,
                ticket_description=ticket.description,
                ticket_category=IssueCategory.INSUFFICIENT_INFORMATION,
                category_confidence=confidence,
                classification_explanation=explanation,
                suspected_root_cause="Unknown due to insufficient information.",
                possible_resolution="Gather missing details before deciding remediation path.",
                evidence=evidence,
                unverified_hypotheses=unverified_hypotheses,
                missing_information=missing_information,
                clarifying_questions=clarifying_questions,
                troubleshooting_steps=troubleshooting_steps,
                handling_level=HandlingLevel.L1,
                escalation_reason=None,
                suggested_next_action="Collect details from reporter and re-analyze.",
            )

        ambiguous = self._is_ambiguous(scores)
        unverified_hypotheses = []
        if ambiguous:
            unverified_hypotheses.append(
                "Signals overlap multiple categories; classification is tentative pending more evidence."
            )

        explanation = (
            f"Detected strongest evidence for {best_profile.category.value} based on keyword and context matches."
            if not ambiguous
            else f"Most evidence points to {best_profile.category.value}, but conflicting signals reduce confidence."
        )

        return AnalyzeTicketResponse(
            ticket_id=ticket.ticket_id,
            ticket_subject=ticket.subject,
            ticket_description=ticket.description,
            ticket_category=best_profile.category,
            category_confidence=confidence,
            classification_explanation=explanation,
            suspected_root_cause=best_profile.suspected_root_cause,
            possible_resolution=best_profile.possible_resolution,
            evidence=evidence,
            unverified_hypotheses=unverified_hypotheses,
            missing_information=[],
            clarifying_questions=[],
            troubleshooting_steps=list(best_profile.troubleshooting_steps),
            handling_level=best_profile.handling_level,
            escalation_reason=best_profile.escalation_reason,
            suggested_next_action=best_profile.next_action,
        )

    def _score(self, texts: list[str]) -> dict[IssueCategory, int]:
        lowered = " \n".join(texts).lower()
        scores: dict[IssueCategory, int] = {profile.category: 0 for profile in self.PROFILES}
        for profile in self.PROFILES:
            for keyword in profile.keywords:
                occurrences = len(re.findall(re.escape(keyword), lowered))
                scores[profile.category] += occurrences
        return scores

    def _pick_profile(self, scores: dict[IssueCategory, int], texts: list[str]) -> tuple[CategoryProfile, float]:
        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_category, top_score = sorted_scores[0]
        second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

        if top_score == 0:
            return self._insufficient_profile(), 0.2

        text_length = len(" ".join(texts).strip())
        margin = top_score - second_score
        if text_length < 30 or margin <= 0:
            return self._insufficient_profile(), 0.25

        confidence = min(0.95, 0.45 + (top_score * 0.1) + (0.05 if margin >= 2 else 0.0))
        if margin == 1:
            confidence = min(confidence, 0.62)

        profile = next(profile for profile in self.PROFILES if profile.category == top_category)
        return profile, round(confidence, 2)

    @staticmethod
    def _is_ambiguous(scores: dict[IssueCategory, int]) -> bool:
        top_two = sorted(scores.values(), reverse=True)[:2]
        return len(top_two) == 2 and top_two[0] > 0 and (top_two[0] - top_two[1]) <= 1

    @staticmethod
    def _extract_evidence(profile: CategoryProfile, texts: list[str]) -> list[str]:
        evidence: list[str] = []
        for text in texts:
            lowered = text.lower()
            for keyword in profile.keywords:
                if keyword in lowered:
                    evidence.append(f"Matched keyword '{keyword}' in: {text}")
                    break
        return evidence[:6]

    def _insufficient_profile(self) -> CategoryProfile:
        return CategoryProfile(
            category=IssueCategory.INSUFFICIENT_INFORMATION,
            keywords=tuple(),
            handling_level=HandlingLevel.L1,
            suspected_root_cause="Unknown",
            possible_resolution="Collect details",
            escalation_reason=None,
            troubleshooting_steps=tuple(),
            next_action="Collect additional evidence.",
        )
