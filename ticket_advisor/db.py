from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import pyodbc
from dotenv import load_dotenv


class DatabaseConfigError(RuntimeError):
    pass


class TicketRepository:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    @classmethod
    def from_env(cls, root: Path) -> "TicketRepository":
        load_dotenv(root / ".env", override=False)
        server = os.getenv("DB_SERVER", "").strip()
        database = os.getenv("DB_NAME", "").strip()
        driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server").strip()
        auth = os.getenv("DB_AUTH_MODE", "windows").strip().lower()
        if not server or not database:
            raise DatabaseConfigError("DB_SERVER and DB_NAME must be set in .env.")
        parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={server}",
            f"DATABASE={database}",
            f"Encrypt={os.getenv('DB_ENCRYPT', 'yes')}",
            f"TrustServerCertificate={os.getenv('DB_TRUST_SERVER_CERTIFICATE', 'yes')}",
            f"Connection Timeout={os.getenv('DB_TIMEOUT', '10')}",
        ]
        if auth in {"windows", "trusted", "integrated", "sspi"}:
            parts.append("Trusted_Connection=yes")
        elif auth in {"sql", "sqlserver", "uid_pwd"}:
            user = os.getenv("DB_USER", "").strip()
            password = os.getenv("DB_PASSWORD", "")
            if not user or not password:
                raise DatabaseConfigError("DB_AUTH_MODE=sql requires DB_USER and DB_PASSWORD.")
            parts.extend([f"UID={user}", f"PWD={password}"])
        else:
            raise DatabaseConfigError("DB_AUTH_MODE must be 'windows' or 'sql'.")
        return cls(";".join(parts) + ";")

    def _connect(self):
        return pyodbc.connect(self.connection_string, timeout=10)

    def check_connection(self) -> dict[str, Any]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DB_NAME()")
            database = cur.fetchone()[0]
            cur.execute("SELECT OBJECT_ID('dbo.Tickets', 'U')")
            exists = cur.fetchone()[0] is not None
        return {"connected": True, "database": database, "tickets_table_exists": exists}

    def list_tickets(self, limit: int = 500) -> list[dict[str, Any]]:
        # Only selects known ticket columns and tolerates optional columns not present in some deployments.
        sql = """
        SELECT TOP (?) *
        FROM dbo.Tickets
        ORDER BY Id DESC
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, limit)
            names = [col[0] for col in cur.description]
            rows = cur.fetchall()
        results = []
        for row in rows:
            item = {names[i]: row[i] for i in range(len(names))}
            # Keep UI/LLM payload bounded and serializable.
            cleaned = {}
            for key, value in item.items():
                if value is None or isinstance(value, (str, int, float, bool)):
                    cleaned[key] = value
                elif hasattr(value, "isoformat"):
                    cleaned[key] = value.isoformat()
                else:
                    cleaned[key] = str(value)
            results.append(cleaned)
        return results
