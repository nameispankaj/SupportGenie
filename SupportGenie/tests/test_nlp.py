"""
Unit tests for the Rule-Based NLP Service (tests/test_nlp.py).
Verifies:
- Accurate classification across all 8 required ticket categories
- Exact alignment with all 10 seed tickets from JotDeskBuddy_Test
- Handling of tickets with insufficient information
- Generation of root-cause hypotheses, resolution steps, rule-based confidence scores,
  matched evidence, missing information checklists, and historical ticket matching.
"""

import unittest
from supportgenie.services.nlp_service import NLPService, VALID_CATEGORIES


SEED_TICKETS = [
    {
        "TicketId": 1,
        "Subject": "Purchase order page shows an error after saving",
        "Description": (
            "After clicking Save on a purchase order, the page displays an unexpected error. "
            "The user reproduced it twice. No error code or timestamp has been supplied."
        ),
        "Category": "Product Bug",
        "ModuleName": "Purchase Orders",
        "ProjectName": "Jot ERP",
        "Status": "Open",
    },
    {
        "TicketId": 2,
        "Subject": "Created purchase order is missing from Procurement Index",
        "Description": (
            "PO DEMO-1002 was reportedly created successfully but is not visible in the Procurement Index. "
            "The active filters and purchase order status have not yet been checked."
        ),
        "Category": "Data Issue",
        "ModuleName": "Procurement Index",
        "ProjectName": "Jot ERP",
        "Status": "Open",
    },
    {
        "TicketId": 3,
        "Subject": "Approval workflow skips department approver",
        "Description": (
            "Purchase requests appear to move directly to the next approval step. "
            "The reporter suspects that a department approval rule changed recently. "
            "Configuration evidence is not yet available."
        ),
        "Category": "Configuration Issue",
        "ModuleName": "Purchase Orders",
        "ProjectName": "Jot ERP",
        "Status": "Open",
    },
    {
        "TicketId": 4,
        "Subject": "Purchase Manager cannot open User Administration",
        "Description": (
            "A Purchase Manager receives Access Denied when opening User Administration. "
            "Other pages work. The user's assigned role and effective permissions have not been checked."
        ),
        "Category": "Permission Issue",
        "ModuleName": "User Administration",
        "ProjectName": "Jot ERP",
        "Status": "Open",
    },
    {
        "TicketId": 5,
        "Subject": "External supplier API requests time out",
        "Description": (
            "Supplier synchronization fails intermittently with a timeout. "
            "Request IDs, timestamps and service logs have not been provided. "
            "Possible causes include the remote endpoint, network, or local timeout configuration."
        ),
        "Category": "Integration Issue",
        "ModuleName": "External API Integration",
        "ProjectName": "Integration Services",
        "Status": "Open",
    },
    {
        "TicketId": 6,
        "Subject": "Closed purchase orders are not in the default list",
        "Description": (
            "The default Procurement Index displays active orders only. "
            "Closed orders can be found by selecting the status filter. "
            "The reporter expected closed orders to appear without changing filters."
        ),
        "Category": "Expected Behaviour",
        "ModuleName": "Procurement Index",
        "ProjectName": "Jot ERP",
        "Status": "Closed",
        "ResolutionRemark": "Documented default-list behaviour explained to the reporter.",
    },
    {
        "TicketId": 7,
        "Subject": "Add bulk export to inventory page",
        "Description": (
            "The user requests an option to export all filtered inventory records to Excel. "
            "No existing export feature is reported as broken."
        ),
        "Category": "Change Request",
        "ModuleName": "Inventory",
        "ProjectName": "Jot ERP",
        "Status": "Open",
    },
    {
        "TicketId": 8,
        "Subject": "Application is not working",
        "Description": (
            "It does not work. Please fix it. "
            "The module, steps, expected result, actual result and error message are missing."
        ),
        "Category": "Insufficient Information",
        "ModuleName": None,
        "ProjectName": "Jot ERP",
        "Status": "Open",
    },
    {
        "TicketId": 9,
        "Subject": "Inventory quantity differs from delivery report",
        "Description": (
            "The inventory screen shows 120 units, while a delivery report shows 102 units for the same demo item. "
            "The effective date, warehouse and transaction history need to be compared."
        ),
        "Category": "Data Issue",
        "ModuleName": "Vessel Reports",
        "ProjectName": "Fleet Operations",
        "Status": "In Progress",
    },
    {
        "TicketId": 10,
        "Subject": "User requests a new approval notification",
        "Description": (
            "The client wants an email notification when a purchase request reaches the final approval step. "
            "No existing notification is reported to be failing."
        ),
        "Category": "Change Request",
        "ModuleName": "Purchase Orders",
        "ProjectName": "Jot ERP",
        "Status": "Open",
    },
]


class TestNLPService(unittest.TestCase):
    def setUp(self) -> None:
        self.nlp = NLPService()

    def test_all_eight_categories_and_ten_seed_tickets(self) -> None:
        """Verify that every seed ticket in _Test classifies into its exact expected category."""
        covered_categories = set()
        for ticket in SEED_TICKETS:
            analysis = self.nlp.analyze_ticket(ticket, historical_tickets=SEED_TICKETS)
            expected = ticket["Category"]
            self.assertEqual(
                analysis["predicted_category"],
                expected,
                msg=f"Ticket #{ticket['TicketId']} ('{ticket['Subject']}') misclassified as {analysis['predicted_category']} instead of {expected}",
            )
            covered_categories.add(analysis["predicted_category"])
            self.assertIn("Hypothesis", analysis["root_cause"])
            self.assertTrue(len(analysis["resolution_steps"]) >= 1)
            self.assertTrue(0.35 <= analysis["confidence_score"] <= 0.95)
            self.assertIn("not a statistically calibrated probability", analysis["confidence_explanation"])

        self.assertEqual(covered_categories, set(VALID_CATEGORIES))

    def test_insufficient_information_on_short_or_empty_ticket(self) -> None:
        """Tickets with minimal or empty descriptions must be classified as Insufficient Information."""
        short_ticket = {
            "TicketId": 99,
            "Subject": "Help",
            "Description": "Broken",
            "ModuleName": None,
        }
        result = self.nlp.analyze_ticket(short_ticket)
        self.assertEqual(result["predicted_category"], "Insufficient Information")
        self.assertTrue(len(result["missing_information"]) >= 3)
        self.assertTrue(
            any("module" in item.lower() for item in result["missing_information"])
        )

    def test_historical_ticket_assistance_finds_relevant_matches(self) -> None:
        """Analyzing a Data Issue or Change Request should surface related historical tickets."""
        ticket_2 = SEED_TICKETS[1]  # Data Issue in Procurement Index
        result = self.nlp.analyze_ticket(ticket_2, historical_tickets=SEED_TICKETS)
        hist = result["historical_tickets"]
        self.assertTrue(len(hist) >= 1)
        matched_ids = [h["ticket_id"] for h in hist]
        # Should match Ticket #9 (Data Issue) or Ticket #6 (Same module: Procurement Index)
        self.assertTrue(9 in matched_ids or 6 in matched_ids)

    def test_missing_information_extracted_from_followup_history(self) -> None:
        """Follow-up remarks containing 'Awaiting...' or 'Pending...' should be surfaced in missing_information."""
        ticket_1 = SEED_TICKETS[0]
        history = {
            "followups": [
                {"Remarks": "Pending reproduction with browser console and server logs."}
            ]
        }
        result = self.nlp.analyze_ticket(ticket_1, historical_tickets=[], ticket_history=history)
        self.assertTrue(
            any("Pending reproduction" in item for item in result["missing_information"])
        )


if __name__ == "__main__":
    unittest.main()
