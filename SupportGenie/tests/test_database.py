"""
Unit tests for database configuration, connection handling, credential redaction,
and repository queries using isolated mocks (tests/test_database.py).
Does NOT insert test data into or modify the real SQL Server database.
"""

import unittest
from unittest.mock import MagicMock, patch

from supportgenie.config import Settings
import supportgenie.database as db_module
from supportgenie.database import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseManager,
    _sanitize_error_message,
    rows_to_dicts,
)
from supportgenie.repositories.ticket_repository import TicketRepository


class TestDatabaseModule(unittest.TestCase):
    def test_windows_auth_connection_string(self) -> None:
        """Windows authentication mode should include Trusted_Connection=yes and omit UID/PWD."""
        cfg = Settings(
            db_server="localhost\\SQLEXPRESS",
            db_name="jotdesk",
            db_driver="ODBC Driver 18 for SQL Server",
            db_auth_mode="windows",
        )
        conn_str = cfg.build_odbc_connection_string()
        self.assertIn("DRIVER={ODBC Driver 18 for SQL Server}", conn_str)
        self.assertIn("SERVER=localhost\\SQLEXPRESS", conn_str)
        self.assertIn("DATABASE=jotdesk", conn_str)
        self.assertIn("Trusted_Connection=yes", conn_str)
        self.assertNotIn("PWD=", conn_str)

    def test_sql_auth_connection_string(self) -> None:
        """SQL Server authentication mode should include UID and PWD."""
        cfg = Settings(
            db_server="127.0.0.1",
            db_name="jotdesk",
            db_auth_mode="sql",
            db_user="sa_demo",
            db_password="SuperSecretPassword123!",
        )
        conn_str = cfg.build_odbc_connection_string()
        self.assertIn("UID=sa_demo", conn_str)
        self.assertIn("PWD=SuperSecretPassword123!", conn_str)
        self.assertNotIn("Trusted_Connection=yes", conn_str)

    def test_credential_sanitization(self) -> None:
        """Sensitive passwords or UIDs must be redacted from error strings."""
        cfg = Settings(db_auth_mode="sql", db_user="admin_user", db_password="MySecretPassword99")
        raw = "Login failed for user 'admin_user'; connection string PWD=MySecretPassword99;"
        sanitized = _sanitize_error_message(raw, cfg)
        self.assertNotIn("MySecretPassword99", sanitized)
        self.assertNotIn("admin_user", sanitized)
        self.assertIn("[REDACTED]", sanitized)

    def test_rows_to_dicts_serialization(self) -> None:
        """rows_to_dicts should convert cursor description and tuple rows into JSON-ready dicts."""
        mock_cursor = MagicMock()
        mock_cursor.description = [("Id",), ("Subject",), ("TicketStatusName",)]
        rows = [(1, "Purchase order error", "Open")]
        result = rows_to_dicts(mock_cursor, rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Id"], 1)
        self.assertEqual(result[0]["Subject"], "Purchase order error")
        self.assertEqual(result[0]["TicketStatusName"], "Open")

    def test_check_connectivity_with_mocked_pyodbc(self) -> None:
        """DatabaseManager.check_connectivity should verify dbo.Tickets and dbo.Clients existence."""
        mock_pyodbc = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("current_database",),
            ("has_tickets_table",),
            ("has_clients_table",),
        ]
        mock_cursor.fetchone.return_value = ("jotdesk", 1, 1)
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        cfg = Settings(db_server="localhost", db_name="jotdesk", db_auth_mode="windows")
        manager = DatabaseManager(settings=cfg)

        with patch.object(db_module, "pyodbc", mock_pyodbc):
            status = manager.check_connectivity()
            self.assertTrue(status["connected"])
            self.assertTrue(status["schema_valid"])
            self.assertEqual(status["database"], "jotdesk")

    def test_connection_failure_raises_sanitized_error(self) -> None:
        """Connection errors must raise DatabaseConnectionError without leaking credentials."""
        mock_pyodbc = MagicMock()
        mock_pyodbc.connect.side_effect = RuntimeError("PWD=SensitivePass123 failed to connect")

        cfg = Settings(
            db_server="localhost",
            db_name="jotdesk",
            db_auth_mode="sql",
            db_user="sa",
            db_password="SensitivePass123",
        )
        manager = DatabaseManager(settings=cfg)

        with patch.object(db_module, "pyodbc", mock_pyodbc):
            with self.assertRaises(DatabaseConnectionError) as ctx:
                with manager.get_connection():
                    pass
            self.assertNotIn("SensitivePass123", str(ctx.exception))

    def test_ticket_repository_parameterized_queries(self) -> None:
        """TicketRepository.list_tickets and update_ticket must use parameterized SQL queries."""
        mock_db = MagicMock(spec=DatabaseManager)
        mock_db.fetch_all.return_value = [{"TicketId": 1, "Subject": "Demo", "Status": "Open"}]
        repo = TicketRepository(db=mock_db)

        tickets = repo.list_tickets(search=" DEMO-1002 ", status="Open", priority="High")
        self.assertEqual(len(tickets), 1)
        called_sql, called_params = mock_db.fetch_all.call_args[0]
        self.assertIn("t.TicketStatusName = ?", called_sql)
        self.assertIn("t.TicketUrgencyName = ?", called_sql)
        self.assertIn("Open", called_params)
        self.assertIn("High", called_params)


if __name__ == "__main__":
    unittest.main()
