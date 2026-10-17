from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from datetime import datetime
import re
from typing import Any

from supportgenie.config import settings
from supportgenie.data.synthetic_tickets import SYNTHETIC_HISTORY, SYNTHETIC_TICKETS
from supportgenie.db.models import SchemaTable, TicketHistoryRecord, TicketRecord
from supportgenie.schemas import DashboardResponse, TicketFilterParams

try:  # pragma: no cover - import covered in integration usage
    import pyodbc
except Exception:  # pragma: no cover - defensive fallback for environments without ODBC runtime
    pyodbc = None


class RepositoryError(Exception):
    pass


class TicketNotFoundError(RepositoryError):
    pass


class SchemaUnavailableError(RepositoryError):
    pass


class TicketRepository(ABC):
    @abstractmethod
    def health(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def dashboard(self) -> DashboardResponse:
        raise NotImplementedError

    @abstractmethod
    def list_tickets(
        self,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
        filters: TicketFilterParams,
    ) -> tuple[int, list[TicketRecord]]:
        raise NotImplementedError

    @abstractmethod
    def get_ticket(self, ticket_id: str) -> TicketRecord:
        raise NotImplementedError

    @abstractmethod
    def get_ticket_history(self, ticket_id: str) -> list[TicketHistoryRecord]:
        raise NotImplementedError


class InMemoryTicketRepository(TicketRepository):
    ALLOWED_SORT_FIELDS = {
        "ticket_id",
        "subject",
        "client",
        "project",
        "module",
        "status",
        "urgency",
        "assigned_support_associate",
        "report_date",
    }

    def __init__(self) -> None:
        self._tickets = [TicketRecord.model_validate(item) for item in SYNTHETIC_TICKETS]

    def health(self) -> str:
        return "ok"

    def dashboard(self) -> DashboardResponse:
        total = len(self._tickets)
        status_counts = Counter((ticket.status or "").lower() for ticket in self._tickets)
        urgency_counts = Counter(ticket.urgency or "Unknown" for ticket in self._tickets)
        return DashboardResponse(
            total_tickets=total,
            open_tickets=status_counts.get("open", 0),
            in_progress_tickets=status_counts.get("in progress", 0),
            closed_tickets=status_counts.get("closed", 0),
            tickets_by_urgency=dict(urgency_counts),
            tickets_by_category={},
        )

    def list_tickets(
        self,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
        filters: TicketFilterParams,
    ) -> tuple[int, list[TicketRecord]]:
        if sort_by not in self.ALLOWED_SORT_FIELDS:
            raise RepositoryError(f"Unsupported sort field: {sort_by}")

        filtered = [ticket for ticket in self._tickets if self._match(ticket, filters)]

        reverse = sort_dir == "desc"
        filtered.sort(key=lambda item: self._sort_value(item, sort_by), reverse=reverse)

        total_count = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return total_count, filtered[start:end]

    def get_ticket(self, ticket_id: str) -> TicketRecord:
        for ticket in self._tickets:
            if ticket.ticket_id == ticket_id:
                return ticket
        raise TicketNotFoundError(f"Ticket '{ticket_id}' not found")

    def get_ticket_history(self, ticket_id: str) -> list[TicketHistoryRecord]:
        self.get_ticket(ticket_id)
        entries = SYNTHETIC_HISTORY.get(ticket_id, [])
        return [
            TicketHistoryRecord(
                ticket_id=ticket_id,
                source=item["source"],
                message=item["message"],
                author=item.get("author"),
                metadata=item.get("metadata", {}),
            )
            for item in entries
        ]

    @staticmethod
    def _sort_value(ticket: TicketRecord, field: str) -> Any:
        value = getattr(ticket, field)
        if value is None:
            return ""
        return value

    @staticmethod
    def _contains(value: str | None, term: str | None) -> bool:
        if not term:
            return True
        if not value:
            return False
        return term.lower() in value.lower()

    def _match(self, ticket: TicketRecord, filters: TicketFilterParams) -> bool:
        if filters.ticket_id and ticket.ticket_id != filters.ticket_id:
            return False
        if not self._contains(ticket.subject, filters.subject):
            return False
        if not self._contains(ticket.client, filters.client):
            return False
        if not self._contains(ticket.project, filters.project):
            return False
        if not self._contains(ticket.module, filters.module):
            return False
        if not self._contains(ticket.status, filters.status):
            return False
        if not self._contains(ticket.urgency, filters.urgency):
            return False
        if filters.start_date and ticket.report_date and ticket.report_date < filters.start_date:
            return False
        if filters.end_date and ticket.report_date and ticket.report_date > filters.end_date:
            return False
        return True


class SqlServerTicketRepository(TicketRepository):
    IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(self) -> None:
        if pyodbc is None:
            raise RepositoryError("pyodbc is not available. Install dependencies and ODBC driver.")
        self._connection_string = self._build_connection_string()
        self._tables = self._load_tables()
        self._mapping = self._build_mapping()

    def health(self) -> str:
        with self._connect() as conn:
            conn.execute("SELECT 1")
        return "ok"

    def dashboard(self) -> DashboardResponse:
        status_col = self._mapping["status"]
        urgency_col = self._mapping["urgency"]
        table = self._safe_identifier(settings.tickets_table)

        with self._connect() as conn:
            total = conn.execute(f"SELECT COUNT(1) FROM {table}").fetchone()[0]
            rows = conn.execute(
                f"SELECT {status_col}, COUNT(1) FROM {table} GROUP BY {status_col}"
            ).fetchall()
            urgency_rows = conn.execute(
                f"SELECT {urgency_col}, COUNT(1) FROM {table} GROUP BY {urgency_col}"
            ).fetchall()

        status_counts = {str(row[0]).lower() if row[0] is not None else "": int(row[1]) for row in rows}
        return DashboardResponse(
            total_tickets=int(total),
            open_tickets=status_counts.get("open", 0),
            in_progress_tickets=status_counts.get("in progress", 0),
            closed_tickets=status_counts.get("closed", 0),
            tickets_by_urgency={str(row[0] or "Unknown"): int(row[1]) for row in urgency_rows},
            tickets_by_category={},
        )

    def list_tickets(
        self,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
        filters: TicketFilterParams,
    ) -> tuple[int, list[TicketRecord]]:
        if sort_by not in self._mapping:
            raise RepositoryError(f"Unsupported sort field: {sort_by}")

        where_sql, params = self._build_filter_sql(filters)
        table = self._safe_identifier(settings.tickets_table)
        sort_col = self._mapping[sort_by]
        offset = (page - 1) * page_size
        direction = "DESC" if sort_dir == "desc" else "ASC"

        select_sql = (
            f"SELECT {self._select_columns_sql()} FROM {table} {where_sql} "
            f"ORDER BY {sort_col} {direction} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        )
        count_sql = f"SELECT COUNT(1) FROM {table} {where_sql}"

        with self._connect() as conn:
            total = conn.execute(count_sql, params).fetchone()[0]
            rows = conn.execute(select_sql, (*params, offset, page_size)).fetchall()

        return int(total), [self._row_to_ticket(row) for row in rows]

    def get_ticket(self, ticket_id: str) -> TicketRecord:
        table = self._safe_identifier(settings.tickets_table)
        sql = (
            f"SELECT {self._select_columns_sql()} FROM {table} "
            f"WHERE {self._mapping['ticket_id']} = ?"
        )
        with self._connect() as conn:
            row = conn.execute(sql, (ticket_id,)).fetchone()
        if not row:
            raise TicketNotFoundError(f"Ticket '{ticket_id}' not found")
        return self._row_to_ticket(row)

    def get_ticket_history(self, ticket_id: str) -> list[TicketHistoryRecord]:
        self.get_ticket(ticket_id)
        history: list[TicketHistoryRecord] = []
        queries = [
            (settings.ticketchat_table, "TicketChat"),
            (settings.ticketfollowups_table, "TicketFollowups"),
            (settings.ticketemails_table, "TicketEmailMessages"),
        ]

        for table_name, source in queries:
            table_meta = self._table_meta(table_name)
            if not table_meta:
                continue

            id_column = self._pick_column(table_meta.columns, ["ticket_id", "ticketid", "ticket_no"])
            message_column = self._pick_column(table_meta.columns, ["message", "body", "details", "description", "content"])
            if not id_column or not message_column:
                continue

            created_column = self._pick_column(table_meta.columns, ["created_at", "createdon", "created_date", "date_created"])
            author_column = self._pick_column(table_meta.columns, ["author", "created_by", "sender", "user_name"])

            columns = [id_column, message_column]
            if created_column:
                columns.append(created_column)
            if author_column:
                columns.append(author_column)

            quoted_columns = ", ".join(self._safe_identifier(col) for col in columns)
            sql = (
                f"SELECT {quoted_columns} FROM {self._safe_identifier(table_name)} "
                f"WHERE {self._safe_identifier(id_column)} = ?"
            )

            with self._connect() as conn:
                rows = conn.execute(sql, (ticket_id,)).fetchall()

            for row in rows:
                created_index = 2 if created_column else None
                author_index = 3 if author_column and created_column else (2 if author_column else None)
                history.append(
                    TicketHistoryRecord(
                        ticket_id=ticket_id,
                        source=source,
                        message=str(row[1]),
                        created_at=row[created_index] if created_index is not None else None,
                        author=str(row[author_index]) if author_index is not None and row[author_index] is not None else None,
                    )
                )

        return history

    def _build_filter_sql(self, filters: TicketFilterParams) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        exact_fields = {
            "ticket_id": filters.ticket_id,
            "status": filters.status,
            "urgency": filters.urgency,
        }
        for key, value in exact_fields.items():
            if value:
                clauses.append(f"{self._mapping[key]} = ?")
                params.append(value)

        like_fields = {
            "subject": filters.subject,
            "client": filters.client,
            "project": filters.project,
            "module": filters.module,
        }
        for key, value in like_fields.items():
            if value:
                clauses.append(f"{self._mapping[key]} LIKE ?")
                params.append(f"%{value}%")

        report_date_col = self._mapping.get("report_date")
        if report_date_col and filters.start_date:
            clauses.append(f"{report_date_col} >= ?")
            params.append(filters.start_date)
        if report_date_col and filters.end_date:
            clauses.append(f"{report_date_col} <= ?")
            params.append(filters.end_date)

        if not clauses:
            return "", params
        return "WHERE " + " AND ".join(clauses), params

    def _build_mapping(self) -> dict[str, str]:
        table_meta = self._table_meta(settings.tickets_table)
        if not table_meta:
            raise SchemaUnavailableError(
                f"Configured tickets table '{settings.tickets_table}' was not found in SQL Server schema"
            )

        columns = table_meta.columns
        choices = {
            "ticket_id": settings.ticket_id_column,
            "subject": settings.ticket_subject_column,
            "description": settings.ticket_description_column,
            "status": settings.ticket_status_column,
            "urgency": settings.ticket_urgency_column,
            "report_date": settings.ticket_reported_at_column,
            "client": settings.ticket_client_column,
            "project": settings.ticket_project_column,
            "module": settings.ticket_module_column,
            "assigned_support_associate": settings.ticket_assignee_column,
            "report_method": settings.ticket_report_method_column,
        }

        mapping: dict[str, str] = {}
        missing_required = []
        required = {"ticket_id", "subject", "description"}

        for logical, configured_name in choices.items():
            if configured_name in columns:
                mapping[logical] = self._safe_identifier(configured_name)
            elif logical in required:
                missing_required.append(configured_name)

        if missing_required:
            raise SchemaUnavailableError(
                "Required configured columns were not found in SQL schema. "
                f"Missing: {', '.join(missing_required)}"
            )

        return mapping

    def _select_columns_sql(self) -> str:
        fields = [
            "ticket_id",
            "subject",
            "description",
            "client",
            "project",
            "module",
            "status",
            "urgency",
            "assigned_support_associate",
            "report_date",
            "report_method",
        ]

        fallback = "NULL"
        projections = [
            f"{self._mapping[key]} AS {self._safe_identifier(key)}" if key in self._mapping else f"{fallback} AS {self._safe_identifier(key)}"
            for key in fields
        ]
        return ", ".join(projections)

    def _row_to_ticket(self, row: Any) -> TicketRecord:
        return TicketRecord(
            ticket_id=str(row[0]),
            subject=str(row[1]),
            description=str(row[2]),
            client=row[3],
            project=row[4],
            module=row[5],
            status=row[6],
            urgency=row[7],
            assigned_support_associate=row[8],
            report_date=row[9],
            report_method=row[10],
        )

    def _load_tables(self) -> dict[str, SchemaTable]:
        sql = (
            "SELECT TABLE_NAME, COLUMN_NAME "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "ORDER BY TABLE_NAME, ORDINAL_POSITION"
        )
        tables: dict[str, list[str]] = {}
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        for table_name, column_name in rows:
            tables.setdefault(str(table_name), []).append(str(column_name))
        return {name: SchemaTable(table_name=name, columns=columns) for name, columns in tables.items()}

    def _table_meta(self, table_name: str) -> SchemaTable | None:
        return self._tables.get(table_name)

    @staticmethod
    def _pick_column(columns: list[str], preferred: list[str]) -> str | None:
        lowered = {item.lower(): item for item in columns}
        for item in preferred:
            if item.lower() in lowered:
                return lowered[item.lower()]
        return None

    def _connect(self):
        return pyodbc.connect(self._connection_string, timeout=settings.sql_server_connection_timeout)

    @classmethod
    def _safe_identifier(cls, name: str) -> str:
        if not cls.IDENTIFIER.match(name):
            raise RepositoryError(f"Unsafe SQL identifier: {name}")
        return f"[{name}]"

    @staticmethod
    def _build_connection_string() -> str:
        server = settings.sql_server_host
        if not server:
            raise RepositoryError("SQL_SERVER_HOST is required when SUPPORTGENIE_DEMO_MODE=false")

        auth_mode = settings.sql_server_auth_mode.lower().strip()
        parts = [
            f"Driver={{{settings.sql_server_driver}}}",
            f"Server={server},{settings.sql_server_port}",
            f"Database={settings.sql_server_database}",
            f"Encrypt={'yes' if settings.sql_server_encrypt else 'no'}",
            f"TrustServerCertificate={'yes' if settings.sql_server_trust_server_certificate else 'no'}",
        ]

        if auth_mode == "windows":
            parts.append("Trusted_Connection=yes")
        elif auth_mode == "sql":
            if not settings.sql_server_username or not settings.sql_server_password:
                raise RepositoryError(
                    "SQL_SERVER_USERNAME and SQL_SERVER_PASSWORD are required for SQL authentication"
                )
            parts.append(f"Uid={settings.sql_server_username}")
            parts.append("Pwd=" + settings.sql_server_password)
        else:
            raise RepositoryError("SQL_SERVER_AUTH_MODE must be 'sql' or 'windows'")

        return ";".join(parts)
