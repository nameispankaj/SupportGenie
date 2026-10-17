"""
Database connectivity module for SupportGenie using pyodbc.
Provides context-managed connections and cursors, parameterized query execution,
row-to-dict serialization suitable for FastAPI JSON responses, and sanitized error handling.
"""

from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
import logging
import re
from typing import Any, Dict, Generator, Iterable, List, Optional, Sequence
import uuid

from supportgenie.config import Settings, get_settings

logger = logging.getLogger(__name__)

try:
    import pyodbc  # type: ignore
except ImportError:  # pragma: no cover
    pyodbc = None  # type: ignore


class DatabaseError(Exception):
    """Sanitized database exception that never exposes connection strings or passwords."""

    def __init__(self, message: str, code: str = "DB_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class DatabaseConnectionError(DatabaseError):
    """Raised when SQL Server connection cannot be established."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="DB_CONNECTION_ERROR")


def _sanitize_error_message(raw_message: str, settings: Optional[Settings] = None) -> str:
    """Strip any potential credentials, UID/PWD tokens, or server secrets from error messages."""
    if not raw_message:
        return "An unexpected database error occurred."
    sanitized = re.sub(r"(?i)(PWD|Password|UID|User\s*ID)\s*=\s*[^;\"'\s]+", r"\1=[REDACTED]", raw_message)
    if settings and settings.db_password:
        sanitized = sanitized.replace(settings.db_password, "[REDACTED]")
    if settings and settings.db_user:
        sanitized = sanitized.replace(settings.db_user, "[REDACTED]")
    return sanitized


def _serialize_value(value: Any) -> Any:
    """Convert SQL Server Python types (datetime, Decimal, UUID, bytes) into JSON-friendly values."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return f"<binary {len(value)} bytes>"
    return value


def rows_to_dicts(cursor: Any, rows: Iterable[Any]) -> List[Dict[str, Any]]:
    """Convert pyodbc cursor rows into a list of dictionaries keyed by column name."""
    if not cursor or not cursor.description:
        return []
    columns = [col[0] for col in cursor.description]
    result: List[Dict[str, Any]] = []
    for row in rows:
        item: Dict[str, Any] = {}
        for idx, col_name in enumerate(columns):
            item[col_name] = _serialize_value(row[idx])
        result.append(item)
    return result


class DatabaseManager:
    """
    Reusable SQL Server connection manager using pyodbc.
    Never modifies schema, drops tables, or seeds dummy records.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings

    @property
    def settings(self) -> Settings:
        return self._settings or get_settings()

    @contextmanager
    def get_connection(self, autocommit: bool = False) -> Generator[Any, None, None]:
        """Context manager that opens and reliably closes a pyodbc connection."""
        cfg = self.settings
        if pyodbc is None:
            raise DatabaseConnectionError(
                "The 'pyodbc' package is not installed or the Microsoft ODBC driver is unavailable."
            )

        try:
            conn_str = cfg.build_odbc_connection_string()
        except ValueError as exc:
            raise DatabaseConnectionError(str(exc)) from exc

        conn = None
        try:
            conn = pyodbc.connect(conn_str, timeout=cfg.db_timeout, autocommit=autocommit)
            yield conn
        except Exception as exc:
            safe_detail = _sanitize_error_message(str(exc), cfg)
            logger.error("SQL Server connection failed: %s", safe_detail)
            raise DatabaseConnectionError(
                "Unable to connect to the configured SQL Server database. "
                "Verify DB_SERVER, DB_NAME, DB_DRIVER, and authentication settings in .env."
            ) from exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def fetch_all(self, query: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        """Execute a parameterized SELECT query and return all rows as dicts."""
        cfg = self.settings
        with self.get_connection(autocommit=True) as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, tuple(params))
                else:
                    cursor.execute(query)
                rows = cursor.fetchall()
                return rows_to_dicts(cursor, rows)
            except DatabaseError:
                raise
            except Exception as exc:
                safe_detail = _sanitize_error_message(str(exc), cfg)
                logger.error("Database query error: %s", safe_detail)
                raise DatabaseError("Database query execution failed.") from exc
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass

    def fetch_one(self, query: str, params: Optional[Sequence[Any]] = None) -> Optional[Dict[str, Any]]:
        """Execute a parameterized SELECT query and return the first row as a dict, or None."""
        cfg = self.settings
        with self.get_connection(autocommit=True) as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, tuple(params))
                else:
                    cursor.execute(query)
                row = cursor.fetchone()
                if row is None:
                    return None
                dicts = rows_to_dicts(cursor, [row])
                return dicts[0] if dicts else None
            except DatabaseError:
                raise
            except Exception as exc:
                safe_detail = _sanitize_error_message(str(exc), cfg)
                logger.error("Database fetch_one error: %s", safe_detail)
                raise DatabaseError("Database query execution failed.") from exc
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass

    def execute_write(
        self,
        query: str,
        params: Optional[Sequence[Any]] = None,
        return_identity: bool = False,
    ) -> Any:
        """
        Execute a parameterized INSERT or UPDATE inside a transaction.
        If return_identity=True, returns the newly generated identity value or scalar result.
        Otherwise returns the number of affected rows.
        """
        cfg = self.settings
        with self.get_connection(autocommit=False) as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, tuple(params))
                else:
                    cursor.execute(query)

                result = None
                if return_identity:
                    row = cursor.fetchone()
                    result = _serialize_value(row[0]) if row is not None else None
                else:
                    result = cursor.rowcount

                conn.commit()
                return result
            except DatabaseError:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise
            except Exception as exc:
                try:
                    conn.rollback()
                except Exception:
                    pass
                safe_detail = _sanitize_error_message(str(exc), cfg)
                logger.error("Database write error: %s", safe_detail)
                raise DatabaseError("Failed to persist record to SQL Server.") from exc
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass

    def execute_transaction(self, statements: Sequence[tuple[str, Sequence[Any]]]) -> None:
        """Execute multiple parameterized write statements atomically in a single transaction."""
        cfg = self.settings
        with self.get_connection(autocommit=False) as conn:
            cursor = conn.cursor()
            try:
                for sql, params in statements:
                    cursor.execute(sql, tuple(params))
                conn.commit()
            except Exception as exc:
                try:
                    conn.rollback()
                except Exception:
                    pass
                safe_detail = _sanitize_error_message(str(exc), cfg)
                logger.error("Database transaction failed: %s", safe_detail)
                raise DatabaseError("Database transaction failed and was rolled back.") from exc
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass

    def check_connectivity(self) -> Dict[str, Any]:
        """
        Verify connectivity to the configured SQL Server database and confirm
        that core tables (dbo.Tickets, dbo.Clients) exist without exposing credentials.
        """
        try:
            row = self.fetch_one(
                """
                SELECT
                    DB_NAME() AS current_database,
                    CASE WHEN OBJECT_ID(N'dbo.Tickets', N'U') IS NOT NULL THEN 1 ELSE 0 END AS has_tickets_table,
                    CASE WHEN OBJECT_ID(N'dbo.Clients', N'U') IS NOT NULL THEN 1 ELSE 0 END AS has_clients_table
                """
            )
            if not row:
                return {
                    "connected": False,
                    "schema_valid": False,
                    "message": "Connected to SQL Server, but verification query returned no data.",
                }
            has_tables = bool(row.get("has_tickets_table")) and bool(row.get("has_clients_table"))
            return {
                "connected": True,
                "schema_valid": has_tables,
                "database": row.get("current_database"),
                "message": (
                    "Connected to SQL Server and verified SupportGenie tables."
                    if has_tables
                    else "Connected to SQL Server, but required dbo.Tickets or dbo.Clients tables were not found."
                ),
            }
        except DatabaseError as exc:
            return {
                "connected": False,
                "schema_valid": False,
                "message": exc.message,
            }


db_manager = DatabaseManager()
