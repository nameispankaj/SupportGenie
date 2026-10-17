"""
API and integration tests for SupportGenie FastAPI endpoints (tests/test_api.py).
Uses FastAPI TestClient and repository mocks so tests run deterministically
without mutating the existing SQL Server database.
"""

import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from supportgenie.config import Settings
from supportgenie.main import app
import supportgenie.api.ticket_routes as ticket_routes_module
import supportgenie.api.email_routes as email_routes_module
from supportgenie.services.ticket_service import TicketService
from supportgenie.services.email_service import EmailService
from tests.test_nlp import SEED_TICKETS


class TestSupportGenieAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.mock_ticket_repo = MagicMock()
        self.mock_email_repo = MagicMock()

        # Configure mock ticket repository with actual JotDeskBuddy_Test structure
        self.mock_ticket_repo.get_dashboard_counts.return_value = {
            "total_tickets": 10,
            "open_tickets": 8,
            "in_progress_tickets": 1,
            "resolved_tickets": 1,
            "high_priority_tickets": 5,
            "assigned_to_associate": 5,
            "current_associate_id": 1,
            "current_associate_name": "Demo L1 Associate",
        }
        self.mock_ticket_repo.get_filter_metadata.return_value = {
            "associates": [{"Id": 1, "Name": "Demo L1 Associate", "Email": "l1@supportgenie-demo.invalid"}],
            "clients": [{"Id": 1, "ClientName": "Northwind Marine Demo"}],
            "modules": [{"Id": 2, "Name": "Purchase Orders", "ProjectName": "Jot ERP"}],
            "statuses": ["Open", "In Progress", "Closed"],
            "categories": ["Product Bug", "Data Issue", "Configuration Issue"],
            "priorities": ["High", "Medium", "Low"],
        }
        self.mock_ticket_repo.list_tickets.return_value = SEED_TICKETS
        self.mock_ticket_repo.get_ticket_by_id.side_effect = lambda tid: next(
            (dict(t) for t in SEED_TICKETS if t["TicketId"] == tid), None
        )
        self.mock_ticket_repo.get_ticket_history.return_value = {
            "ticket_id": 1,
            "chats": [{"Id": 1, "ChatRunningNumber": 1, "Chat": "L1: Please provide time of error.", "AddedByName": "Demo L1 Associate"}],
            "followups": [{"Id": 1, "FollowupRunningNumber": 1, "Remarks": "Pending reproduction.", "AddedByName": "Demo L2 Associate"}],
            "email_messages": [{"Id": 1, "TicketId": 1, "MessageId": "demo-msg-1001-in", "IsOutgoing": False, "AddedByName": "Demo User A"}],
            "update_logs": [],
        }
        self.mock_ticket_repo.get_historical_tickets_for_nlp.return_value = SEED_TICKETS

        # Swap services in routers with mocked repositories
        self.orig_ticket_service = ticket_routes_module.ticket_service
        self.orig_email_service = email_routes_module.email_service

        ticket_routes_module.ticket_service = TicketService(repository=self.mock_ticket_repo)
        email_routes_module.email_service = EmailService(
            repository=self.mock_email_repo,
            settings=Settings(smtp_host="", support_team_email="support-team@supportgenie.local"),
        )

    def tearDown(self) -> None:
        ticket_routes_module.ticket_service = self.orig_ticket_service
        email_routes_module.email_service = self.orig_email_service

    def test_health_endpoint(self) -> None:
        """GET /health should return 200 and explicitly note /health/db for DB verification."""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["database_check_endpoint"], "/health/db")

    def test_dashboard_endpoint(self) -> None:
        """GET /api/dashboard should return real ticket statistics and filter metadata."""
        resp = self.client.get("/api/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["counts"]["total_tickets"], 10)
        self.assertEqual(data["counts"]["open_tickets"], 8)
        self.assertEqual(data["counts"]["in_progress_tickets"], 1)
        self.assertEqual(data["counts"]["resolved_tickets"], 1)

    def test_list_tickets_and_get_valid_ticket(self) -> None:
        """GET /api/tickets and GET /api/tickets/1 should return expected records."""
        resp_list = self.client.get("/api/tickets")
        self.assertEqual(resp_list.status_code, 200)
        self.assertEqual(resp_list.json()["count"], 10)

        resp_detail = self.client.get("/api/tickets/1")
        self.assertEqual(resp_detail.status_code, 200)
        self.assertEqual(resp_detail.json()["ticket"]["TicketId"], 1)

    def test_invalid_and_nonexistent_ticket_ids(self) -> None:
        """Negative/zero ticket IDs should return 400; missing ticket IDs should return 404."""
        resp_neg = self.client.get("/api/tickets/-5")
        self.assertEqual(resp_neg.status_code, 400)

        resp_missing = self.client.get("/api/tickets/9999")
        self.assertEqual(resp_missing.status_code, 404)

        resp_analyze_missing = self.client.post("/api/tickets/9999/analyze")
        self.assertEqual(resp_analyze_missing.status_code, 404)

    def test_analyze_ticket_endpoint(self) -> None:
        """POST /api/tickets/4/analyze should return Permission Issue analysis."""
        resp = self.client.post("/api/tickets/4/analyze")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["predicted_category"], "Permission Issue")
        self.assertIn("Hypothesis", data["root_cause"])
        self.assertTrue(len(data["resolution_steps"]) > 0)

    def test_add_comment_and_status_update_validation(self) -> None:
        """POST /api/tickets/{id}/comments and PATCH /api/tickets/{id}/status validate inputs and persist."""
        self.mock_ticket_repo.add_comment_or_note.return_value = {
            "id": 10,
            "ticket_id": 1,
            "note_type": "followup",
            "running_number": 2,
            "text": "Checked server logs.",
            "added_by_name": "Demo L1 Associate",
        }
        resp_comment = self.client.post(
            "/api/tickets/1/comments",
            json={"text": "Checked server logs.", "note_type": "followup"},
        )
        self.assertEqual(resp_comment.status_code, 201)
        self.assertEqual(resp_comment.json()["status"], "success")

        # Invalid note_type should return 400
        resp_bad_type = self.client.post(
            "/api/tickets/1/comments",
            json={"text": "Test", "note_type": "invalid_type"},
        )
        self.assertEqual(resp_bad_type.status_code, 400)

        # Invalid status name should return 400
        resp_bad_status = self.client.patch(
            "/api/tickets/1/status",
            json={"status": "NonExistentStatus"},
        )
        self.assertEqual(resp_bad_status.status_code, 400)

        # Valid status update
        self.mock_ticket_repo.update_ticket.return_value = {
            "TicketId": 1,
            "Status": "In Progress",
            "Remark": "Investigating logs",
        }
        resp_ok_status = self.client.patch(
            "/api/tickets/1/status",
            json={"status": "In Progress", "remark": "Investigating logs"},
        )
        self.assertEqual(resp_ok_status.status_code, 200)
        self.assertEqual(resp_ok_status.json()["ticket"]["Status"], "In Progress")

    def test_email_send_validation_and_honest_unconfigured_smtp(self) -> None:
        """POST /api/emails/send validates recipient/subject/body and never fakes SMTP delivery."""
        # Invalid email address
        resp_bad = self.client.post(
            "/api/emails/send",
            json={"to": "not-an-email", "subject": "Hello", "body": "Test message"},
        )
        self.assertEqual(resp_bad.status_code, 400)

        # Valid email when SMTP is unconfigured must report sent=False, smtp_configured=False
        resp_unconfigured = self.client.post(
            "/api/emails/send",
            json={
                "to": "support-team@supportgenie.local",
                "subject": "Support Question",
                "body": "Need assistance with PO DEMO-1002.",
                "ticket_id": 2,
            },
        )
        self.assertEqual(resp_unconfigured.status_code, 200)
        body = resp_unconfigured.json()
        self.assertFalse(body["sent"])
        self.assertFalse(body["smtp_configured"])
        self.assertFalse(body["recorded_in_db"])
        self.assertIn("NOT sent", body["status_message"])


if __name__ == "__main__":
    unittest.main()
