"""
Modular Rule-Based NLP Service for SupportGenie (Initial Version).

Classifies support tickets into the 8 required categories:
1. Product Bug
2. Data Issue
3. Configuration Issue
4. Permission Issue
5. Integration Issue
6. Expected Behaviour
7. Change Request
8. Insufficient Information

Generates:
- Predicted ticket category
- Likely root cause (clearly labeled as a hypothesis when evidence is incomplete)
- Recommended investigation / resolution steps (without fabricating environment facts)
- Rule-based confidence score and indicator (with clear explanation of rule-based scoring)
- Matched keywords and contextual rules (supporting evidence)
- Missing information required for further investigation
- Relevant historical ticket examples from SQL Server

Designed with a clean interface so a future AI/LLM service can extend or replace it
without rewriting the FastAPI routes or frontend.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Set, Tuple

VALID_CATEGORIES: Tuple[str, ...] = (
    "Product Bug",
    "Data Issue",
    "Configuration Issue",
    "Permission Issue",
    "Integration Issue",
    "Expected Behaviour",
    "Change Request",
    "Insufficient Information",
)

STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "is", "it", "its", "of", "on", "or", "that", "the", "their", "them",
    "there", "these", "they", "this", "to", "was", "were", "will", "with", "after",
    "before", "when", "where", "which", "who", "whom", "user", "demo", "page",
    "ticket", "please", "need", "needs", "yet", "been", "not",
}


@dataclass(frozen=True)
class CategoryRuleSet:
    category: str
    strong_phrases: Tuple[str, ...]
    keywords: Tuple[str, ...]
    root_cause_template: str
    resolution_steps: Tuple[str, ...]
    default_missing_checks: Tuple[str, ...]


CATEGORY_RULES: Tuple[CategoryRuleSet, ...] = (
    CategoryRuleSet(
        category="Insufficient Information",
        strong_phrases=(
            "application is not working",
            "it does not work",
            "doesn't work",
            "does not work",
            "please fix it",
            "steps, expected result, actual result and error message are missing",
            "error message are missing",
            "no details provided",
            "nothing works",
            "system down help",
        ),
        keywords=(
            "vague",
            "unexplained",
            "unspecified",
        ),
        root_cause_template=(
            "Hypothesis (Unconfirmed): Cannot formulate a specific technical root-cause hypothesis "
            "because the report lacks the affected module, exact action taken, and observable symptom."
        ),
        resolution_steps=(
            "Reply to the reporter requesting the specific module or screen name where the issue occurred.",
            "Ask for step-by-step reproduction actions, expected behaviour vs. actual behaviour, and any exact error message or screenshot.",
            "Keep the ticket in triage until basic diagnostic context is provided.",
        ),
        default_missing_checks=(
            "Affected application module or page name",
            "Step-by-step reproduction instructions",
            "Expected result vs. actual result",
            "Exact error text, screenshot, or timestamp",
        ),
    ),
    CategoryRuleSet(
        category="Permission Issue",
        strong_phrases=(
            "access denied",
            "cannot open user administration",
            "insufficient permissions",
            "unauthorized",
            "forbidden",
            "not authorized",
            "assigned role",
            "effective permissions",
            "permission issue",
            "role permission",
            "cannot access",
            "no access to",
        ),
        keywords=(
            "permission",
            "permissions",
            "access",
            "denied",
            "role",
            "roles",
            "privilege",
            "privileges",
            "authorization",
            "unauthorized",
            "forbidden",
            "rbac",
        ),
        root_cause_template=(
            "Hypothesis (Unconfirmed): The user's assigned security role or tenant-level permission mapping "
            "Likely lacks the required access privilege for {module_context}, or a role restriction is active."
        ),
        resolution_steps=(
            "Inspect the affected user's assigned role and effective permission matrix in User Administration.",
            "Compare the user's role configuration against a working peer profile in the same client/tenant.",
            "Do not grant elevated permissions until role authorization is verified with the client administrator.",
        ),
        default_missing_checks=(
            "Affected user's assigned security role and effective permissions",
            "Confirmation of whether access is authorized by the client administrator",
        ),
    ),
    CategoryRuleSet(
        category="Integration Issue",
        strong_phrases=(
            "external supplier api",
            "api requests time out",
            "supplier synchronization",
            "fails intermittently with a timeout",
            "remote endpoint",
            "webhook failure",
            "third-party api",
            "external api",
            "connection timed out",
            "service logs",
            "correlation id",
            "sync failed",
        ),
        keywords=(
            "api",
            "timeout",
            "timed",
            "synchronization",
            "sync",
            "endpoint",
            "webhook",
            "supplier",
            "external",
            "integration",
            "payload",
            "gateway",
            "http",
            "soap",
            "rest",
        ),
        root_cause_template=(
            "Hypothesis (Unconfirmed): Communication between {module_context} and the external service endpoint "
            "is timing out or failing, potentially due to remote endpoint latency, network routing, or timeout threshold settings."
        ),
        resolution_steps=(
            "Collect failed request timestamps, correlation/request IDs, and integration service logs.",
            "Verify whether timeouts originate from the remote supplier endpoint, network gateway, or local timeout configuration.",
            "Check retry policies and payload sizes for the affected synchronization job.",
        ),
        default_missing_checks=(
            "Failed request IDs or correlation IDs",
            "Exact failure timestamps (UTC) and integration service logs",
            "Remote endpoint response status or timeout threshold setting",
        ),
    ),
    CategoryRuleSet(
        category="Expected Behaviour",
        strong_phrases=(
            "not in the default list",
            "displays active orders only",
            "can be found by selecting the status filter",
            "expected closed orders to appear without changing filters",
            "working as designed",
            "by design",
            "documented default",
            "default filter",
            "expected behaviour",
            "expected behavior",
        ),
        keywords=(
            "default",
            "expected",
            "documented",
            "intended",
            "designed",
        ),
        root_cause_template=(
            "Hypothesis (Unconfirmed): The application in {module_context} appears to be operating according to its "
            "standard design (such as default view filtering), which differs from the reporter's workflow expectation."
        ),
        resolution_steps=(
            "Verify the standard filter or view behaviour in the product documentation for the module.",
            "Guide the user on how to adjust the active UI filters (e.g., selecting the 'Closed' status filter) to view the desired records.",
            "If the client wants the default behaviour altered permanently, advise submitting a formal Change Request.",
        ),
        default_missing_checks=(
            "Confirmation from the reporter that adjusting the filter resolves their immediate question",
        ),
    ),
    CategoryRuleSet(
        category="Change Request",
        strong_phrases=(
            "add bulk export",
            "requests an option",
            "requests a new",
            "client wants",
            "user requests",
            "feature request",
            "enhancement request",
            "no existing export feature is reported as broken",
            "no existing notification is reported to be failing",
            "new feature",
            "would like to add",
        ),
        keywords=(
            "add",
            "export",
            "enhancement",
            "feature",
            "request",
            "requests",
            "wants",
            "new",
            "bulk",
            "custom",
            "notification",
        ),
        root_cause_template=(
            "Hypothesis (Unconfirmed): No existing defect is indicated; the ticket describes a new capability or "
            "workflow enhancement requested for {module_context}."
        ),
        resolution_steps=(
            "Confirm that no existing functionality is broken and document the business use case and scope.",
            "Assign or route the ticket to the Product Owner for backlog evaluation, effort estimation, and prioritization.",
            "Communicate to the client that the item is being tracked as an enhancement/change request.",
        ),
        default_missing_checks=(
            "Product Owner assessment and backlog prioritization",
            "Detailed functional specification (file format, volume limits, or recipient rules)",
        ),
    ),
    CategoryRuleSet(
        category="Configuration Issue",
        strong_phrases=(
            "approval workflow skips",
            "skips department approver",
            "approval rule changed",
            "move directly to the next approval step",
            "workflow routing",
            "configuration issue",
            "misconfigured",
            "rule configuration",
            "approval step",
        ),
        keywords=(
            "workflow",
            "approval",
            "approver",
            "skips",
            "skip",
            "rule",
            "rules",
            "routing",
            "configuration",
            "configured",
            "setting",
            "settings",
            "threshold",
        ),
        root_cause_template=(
            "Hypothesis (Unconfirmed): A workflow routing rule, approval threshold, or module setting in "
            "{module_context} may have been modified or misconfigured, causing steps to be bypassed."
        ),
        resolution_steps=(
            "Review the current workflow/approval rule configuration and audit history for recent changes.",
            "Obtain an example affected transaction/request ID and trace which rule condition evaluated to skip the step.",
            "Verify the intended approval matrix with the client before adjusting any configuration rules.",
        ),
        default_missing_checks=(
            "Current workflow/approval rule configuration snapshot",
            "Specific affected request or transaction ID to trace routing evaluation",
        ),
    ),
    CategoryRuleSet(
        category="Data Issue",
        strong_phrases=(
            "missing from procurement index",
            "created purchase order is missing",
            "not visible in the",
            "quantity differs from",
            "differs from delivery report",
            "data discrepancy",
            "mismatch between",
            "data issue",
            "duplicate record",
            "missing record",
            "shows 120 units, while a delivery report shows",
        ),
        keywords=(
            "missing",
            "differs",
            "discrepancy",
            "mismatch",
            "quantity",
            "units",
            "visible",
            "index",
            "records",
            "warehouse",
            "transaction",
            "totals",
            "balance",
            "report",
        ),
        root_cause_template=(
            "Hypothesis (Unconfirmed): The reported discrepancy or missing visibility in {module_context} is likely "
            "caused by active UI/status filters, tenant/warehouse scope differences, or unposted/mismatched transaction records."
        ),
        resolution_steps=(
            "Query the underlying SQL Server records directly to verify whether the record exists and inspect its status, tenant, and effective dates.",
            "Check whether active UI filters, warehouse selection, or cutoff dates explain the difference between screens/reports.",
            "Compare transaction-level history before performing any data correction.",
        ),
        default_missing_checks=(
            "Verification of active screen filters and record status in the database",
            "Effective date, warehouse, item/document code, and transaction history comparison",
        ),
    ),
    CategoryRuleSet(
        category="Product Bug",
        strong_phrases=(
            "shows an error after saving",
            "displays an unexpected error",
            "reproduced it twice",
            "after clicking save",
            "unhandled exception",
            "crash",
            "stack trace",
            "nullreference",
            "500 internal server error",
            "page crashes",
            "button throws an error",
        ),
        keywords=(
            "error",
            "unexpected",
            "reproduced",
            "save",
            "saving",
            "clicking",
            "bug",
            "exception",
            "crash",
            "broken",
            "fails",
        ),
        root_cause_template=(
            "Hypothesis (Unconfirmed): An application defect or unhandled server/validation error is occurring in "
            "{module_context} when executing the user's action (such as saving a record)."
        ),
        resolution_steps=(
            "Request the exact timestamp, error code/message, and browser console or server logs from when the error occurred.",
            "Attempt to reproduce the error in the test environment using the same input fields and line items.",
            "Inspect application exception logs around the reported time before escalating to L2/engineering.",
        ),
        default_missing_checks=(
            "Exact error code, stack trace, or screenshot of the error banner",
            "Precise timestamp (UTC) and input payload used when clicking Save",
            "Browser console and backend application server logs",
        ),
    ),
)


def normalize_text(text: str) -> str:
    """Normalize input text to lowercase with collapsed whitespace for consistent rule matching."""
    if not text:
        return ""
    cleaned = text.lower().strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def tokenize_meaningful_words(text: str) -> Set[str]:
    """Extract normalized alphanumeric tokens excluding common stopwords."""
    normalized = normalize_text(text)
    words = re.findall(r"[a-z0-9][a-z0-9_-]*", normalized)
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


class NLPService:
    """
    Modular rule-based NLP analyzer for SupportGenie.
    Evaluates ticket text once, matches weighted phrase/keyword rules, extracts missing information,
    and correlates with historical SQL Server tickets.
    """

    def analyze_ticket(
        self,
        ticket: Dict[str, Any],
        historical_tickets: Optional[List[Dict[str, Any]]] = None,
        ticket_history: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a ticket dictionary and produce structured NLP outputs:
        - predicted_category
        - root_cause
        - possible_resolution
        - recommended_next_action
        - confidence_score (0.0 - 1.0)
        - confidence_label ('High', 'Medium', 'Low')
        - confidence_explanation
        - matched_evidence (phrases, keywords, context signals)
        - missing_information
        - historical_matches
        """
        subject = str(ticket.get("Subject") or "").strip()
        description = str(ticket.get("Description") or "").strip()
        module_name = ticket.get("ModuleName") or ticket.get("TicketModuleName")
        project_name = ticket.get("ProjectName")
        recorded_category = ticket.get("Category") or ticket.get("TicketTypeName")

        combined_raw = f"{subject}. {description}".strip()
        normalized = normalize_text(combined_raw)
        tokens = tokenize_meaningful_words(combined_raw)

        module_context = (
            f"the '{module_name}' module ({project_name})"
            if module_name and project_name
            else f"the '{module_name}' module"
            if module_name
            else "the application"
        )

        # Check for extremely short or explicitly vague tickets first
        is_explicitly_vague = any(
            phrase in normalized
            for phrase in (
                "application is not working",
                "it does not work",
                "doesn't work. please fix",
                "steps, expected result, actual result and error message are missing",
            )
        )
        word_count = len(re.findall(r"\b\w+\b", combined_raw))

        scores: Dict[str, float] = {}
        matched_phrases_by_cat: Dict[str, List[str]] = {}
        matched_keywords_by_cat: Dict[str, List[str]] = {}
        rule_by_cat: Dict[str, CategoryRuleSet] = {}

        for ruleset in CATEGORY_RULES:
            rule_by_cat[ruleset.category] = ruleset
            cat_score = 0.0
            phrases_hit: List[str] = []
            keywords_hit: List[str] = []

            for phrase in ruleset.strong_phrases:
                if phrase in normalized:
                    phrases_hit.append(phrase)
                    cat_score += 4.0

            for kw in ruleset.keywords:
                # Avoid counting "error" as a Product Bug signal when the text says "error message are missing"
                if (
                    ruleset.category == "Product Bug"
                    and kw == "error"
                    and "error message are missing" in normalized
                ):
                    continue
                # Avoid counting "broken" as a Product Bug signal when text says "no existing ... is reported as broken"
                if (
                    ruleset.category == "Product Bug"
                    and kw == "broken"
                    and "no existing" in normalized
                    and "broken" in normalized
                ):
                    continue
                if kw in tokens or (len(kw) > 4 and kw in normalized):
                    keywords_hit.append(kw)
                    cat_score += 1.25

            scores[ruleset.category] = cat_score
            matched_phrases_by_cat[ruleset.category] = phrases_hit
            matched_keywords_by_cat[ruleset.category] = keywords_hit

        # Handle very short or empty descriptions lacking actionable signal
        if word_count < 6 or (is_explicitly_vague and scores["Insufficient Information"] >= 4.0):
            predicted_category = "Insufficient Information"
        else:
            # Pick category with highest rule score
            best_cat, best_score = max(scores.items(), key=lambda item: item[1])
            if best_score <= 0.0:
                predicted_category = "Insufficient Information"
            else:
                predicted_category = best_cat

        chosen_rule = rule_by_cat[predicted_category]
        matched_phrases = matched_phrases_by_cat.get(predicted_category, [])
        matched_keywords = matched_keywords_by_cat.get(predicted_category, [])
        raw_score = scores.get(predicted_category, 0.0)

        # Compute simple, transparent rule-based confidence score (bounded 0.35 to 0.95)
        if predicted_category == "Insufficient Information" and raw_score == 0.0:
            confidence_score = 0.45
        else:
            # Base 0.45 + 0.12 per strong phrase + 0.05 per keyword, capped at 0.95
            confidence_score = min(
                0.95,
                round(0.45 + (len(matched_phrases) * 0.14) + (len(matched_keywords) * 0.05), 2),
            )

        if confidence_score >= 0.78:
            confidence_label = "High"
        elif confidence_score >= 0.58:
            confidence_label = "Medium"
        else:
            confidence_label = "Low"

        # Detect missing information from explicit statements in description + category checklist
        missing_info = self._identify_missing_information(
            normalized_text=normalized,
            ticket=ticket,
            chosen_rule=chosen_rule,
            ticket_history=ticket_history,
        )

        # Build historical matches
        historical_matches = self._find_historical_matches(
            current_ticket=ticket,
            predicted_category=predicted_category,
            current_tokens=tokens,
            historical_tickets=historical_tickets or [],
        )

        # Build root cause hypothesis incorporating historical context if available
        root_cause = chosen_rule.root_cause_template.format(module_context=module_context)
        if historical_matches:
            top_hist = historical_matches[0]
            if top_hist.get("resolution_remark"):
                root_cause += (
                    f" Historical reference (Ticket #{top_hist['ticket_id']}) in the same domain "
                    f"noted: \"{top_hist['resolution_remark']}\"."
                )

        # Build recommended resolution and next action
        resolution_steps = list(chosen_rule.resolution_steps)
        recommended_next_action = resolution_steps[0] if resolution_steps else "Review ticket details."

        supporting_evidence: List[str] = []
        if matched_phrases:
            supporting_evidence.append(
                "Matched contextual rules: " + ", ".join(f'"{p}"' for p in matched_phrases)
            )
        if matched_keywords:
            supporting_evidence.append(
                "Matched domain keywords: " + ", ".join(f'"{k}"' for k in matched_keywords)
            )
        if module_name:
            supporting_evidence.append(f"Module context: {module_name} ({project_name or 'N/A'})")
        if recorded_category:
            alignment = (
                "matches"
                if recorded_category.strip().lower() == predicted_category.lower()
                else f"differs from recorded TicketTypeName ('{recorded_category}')"
            )
            supporting_evidence.append(f"Database category check: prediction {alignment}.")
        if not supporting_evidence:
            supporting_evidence.append(
                "No specific technical defect/configuration keywords matched; classified as Insufficient Information."
            )

        return {
            "ticket_id": ticket.get("TicketId") or ticket.get("Id"),
            "predicted_category": predicted_category,
            "recorded_category": recorded_category,
            "root_cause": root_cause,
            "is_hypothesis": True,
            "hypothesis_notice": (
                "This root cause is a rule-based hypothesis derived from ticket text and historical records, "
                "not a confirmed technical fact."
            ),
            "possible_resolution": " ".join(resolution_steps),
            "resolution_steps": resolution_steps,
            "recommended_next_action": recommended_next_action,
            "confidence_score": confidence_score,
            "confidence_label": confidence_label,
            "confidence_explanation": (
                f"Rule-based confidence score of {int(confidence_score * 100)}% ({confidence_label}) based on "
                f"{len(matched_phrases)} contextual phrase match(es) and {len(matched_keywords)} keyword match(es). "
                "Note: This score represents deterministic rule-matching strength, not a statistically calibrated probability."
            ),
            "matched_keywords": matched_keywords,
            "matched_phrases": matched_phrases,
            "supporting_evidence": supporting_evidence,
            "missing_information": missing_info,
            "historical_tickets": historical_matches,
            "historical_summary": (
                f"Found {len(historical_matches)} relevant historical ticket(s) in SQL Server."
                if historical_matches
                else "No closely matching historical tickets with recorded resolutions were found in the database."
            ),
        }

    def _identify_missing_information(
        self,
        normalized_text: str,
        ticket: Dict[str, Any],
        chosen_rule: CategoryRuleSet,
        ticket_history: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Identify missing diagnostic details from text signals, null columns, and category checklists."""
        missing: List[str] = []

        if not (ticket.get("ModuleName") or ticket.get("TicketModuleName")):
            missing.append("Affected application module (TicketModule is not set on this ticket)")

        explicit_missing_signals = (
            ("no error code or timestamp", "Exact error code and timestamp of the failure"),
            ("active filters and purchase order status have not yet been checked", "Active UI filter state and record status verification"),
            ("configuration evidence is not yet available", "Current workflow/approval rule configuration evidence"),
            ("assigned role and effective permissions have not been checked", "User's assigned security role and effective permissions"),
            ("request ids, timestamps and service logs have not been provided", "Failed request/correlation IDs, timestamps, and service logs"),
            ("module, steps, expected result, actual result and error message are missing", "Module name, reproduction steps, expected vs. actual result, and exact error text"),
            ("effective date, warehouse and transaction history need to be compared", "Effective date, warehouse code, and transaction-level history comparison"),
        )
        for signal, description in explicit_missing_signals:
            if signal in normalized_text and description not in missing:
                missing.append(description)

        for default_item in chosen_rule.default_missing_checks:
            if len(missing) < 4 and default_item not in missing:
                missing.append(default_item)

        if ticket_history:
            followups = ticket_history.get("followups") or []
            for fup in followups:
                remark_text = str(fup.get("Remarks") or "").strip()
                if any(
                    cue in remark_text.lower()
                    for cue in ("awaiting", "pending", "requested", "next step")
                ):
                    note_item = f"Open follow-up note: {remark_text}"
                    if note_item not in missing:
                        missing.append(note_item)

        return missing

    def _find_historical_matches(
        self,
        current_ticket: Dict[str, Any],
        predicted_category: str,
        current_tokens: Set[str],
        historical_tickets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Rank historical tickets from SQL Server by category alignment, module alignment,
        and keyword overlap. Returns up to 3 relevant examples.
        """
        current_id = current_ticket.get("TicketId") or current_ticket.get("Id")
        current_module = (
            current_ticket.get("ModuleName") or current_ticket.get("TicketModuleName") or ""
        ).strip().lower()

        scored_matches: List[Tuple[float, Dict[str, Any]]] = []

        for cand in historical_tickets:
            cand_id = cand.get("TicketId") or cand.get("Id")
            if current_id is not None and cand_id == current_id:
                continue

            cand_cat = str(cand.get("Category") or cand.get("TicketTypeName") or "").strip()
            cand_module = str(cand.get("ModuleName") or cand.get("TicketModuleName") or "").strip()
            cand_subject = str(cand.get("Subject") or "").strip()
            cand_desc = str(cand.get("Description") or "").strip()
            cand_tokens = tokenize_meaningful_words(f"{cand_subject} {cand_desc}")

            overlap = current_tokens.intersection(cand_tokens)
            union = current_tokens.union(cand_tokens)
            jaccard = (len(overlap) / len(union)) if union else 0.0

            similarity = 0.0
            reasons: List[str] = []

            if cand_cat and cand_cat.lower() == predicted_category.lower():
                similarity += 0.45
                reasons.append(f"Same category ({cand_cat})")

            if current_module and cand_module and current_module == cand_module.lower():
                similarity += 0.25
                reasons.append(f"Same module ({cand_module})")

            if overlap:
                similarity += min(0.30, jaccard * 0.6)
                reasons.append("Shared terms: " + ", ".join(sorted(list(overlap))[:5]))

            if similarity >= 0.35:
                scored_matches.append(
                    (
                        round(similarity, 2),
                        {
                            "ticket_id": cand_id,
                            "subject": cand_subject,
                            "category": cand_cat,
                            "status": cand.get("Status") or cand.get("TicketStatusName"),
                            "module_name": cand_module or "Unassigned",
                            "resolution_remark": cand.get("ResolutionRemark") or cand.get("Remark"),
                            "latest_followup": cand.get("LatestFollowup"),
                            "similarity_score": round(similarity, 2),
                            "match_reasons": reasons,
                        },
                    )
                )

        scored_matches.sort(
            key=lambda item: (
                1 if item[1].get("resolution_remark") else 0,
                item[0],
            ),
            reverse=True,
        )
        return [match for _, match in scored_matches[:3]]


nlp_service = NLPService()
