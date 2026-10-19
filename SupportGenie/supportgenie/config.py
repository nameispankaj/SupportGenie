"""
Configuration module for SupportGenie.
Loads database, application, and SMTP settings from .env using python-dotenv.
Never exposes credentials to frontend responses or logs.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root if present
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)


def _str_to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    """Application, SQL Server, and SMTP configuration settings."""

    # Application settings
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    app_debug: bool = _str_to_bool(os.getenv("APP_DEBUG", "false"))
    default_tenant_id: int = int(os.getenv("DEFAULT_TENANT_ID", "1"))
    default_associate_id: int = int(os.getenv("DEFAULT_ASSOCIATE_ID", "1"))
    default_associate_name: str = os.getenv("DEFAULT_ASSOCIATE_NAME", "Demo L1 Associate")

    # SQL Server Database settings
    db_server: str = os.getenv("DB_SERVER", "localhost")
    db_name: str = os.getenv("DB_NAME", "jotdesk")
    db_schema: str = os.getenv("DB_SCHEMA", "dbo")
    db_driver: str = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    db_auth_mode: str = os.getenv("DB_AUTH_MODE", "windows").strip().lower()
    db_user: str = os.getenv("DB_USER", "")
    db_password: str = os.getenv("DB_PASSWORD", "")
    db_trust_server_certificate: str = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes")
    db_encrypt: str = os.getenv("DB_ENCRYPT", "yes")
    db_timeout: int = int(os.getenv("DB_TIMEOUT", "10"))

    # SMTP settings
    smtp_host: str = os.getenv("SMTP_HOST", "").strip()
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = _str_to_bool(os.getenv("SMTP_USE_TLS", "true"), default=True)
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "support@supportgenie.local").strip()
    support_team_email: str = os.getenv("SUPPORT_TEAM_EMAIL", "support-team@supportgenie.local").strip()

    @property
    def is_smtp_configured(self) -> bool:
        """Return True only if an actual SMTP server host is configured."""
        return bool(self.smtp_host and self.smtp_from_email)

    def build_odbc_connection_string(self) -> str:
        """
        Build a Microsoft SQL Server ODBC connection string supporting either
        Windows Authentication (Trusted_Connection=yes) or SQL Server Authentication (UID/PWD).
        """
        driver = self.db_driver.strip()
        if not driver.startswith("{"):
            driver = f"{{{driver}}}"

        parts = [
            f"DRIVER={driver}",
            f"SERVER={self.db_server}",
            f"DATABASE={self.db_name}",
            f"Encrypt={self.db_encrypt}",
            f"TrustServerCertificate={self.db_trust_server_certificate}",
        ]

        auth = self.db_auth_mode.lower()
        if auth in {"windows", "trusted", "integrated", "sspi"}:
            parts.append("Trusted_Connection=yes")
        elif auth in {"sql", "sqlserver", "uid_pwd"}:
            if not self.db_user:
                raise ValueError("DB_AUTH_MODE is set to 'sql', but DB_USER is empty.")
            parts.append(f"UID={self.db_user}")
            parts.append(f"PWD={self.db_password}")
        else:
            raise ValueError(
                f"Unsupported DB_AUTH_MODE '{self.db_auth_mode}'. Expected 'windows' or 'sql'."
            )

        return ";".join(parts) + ";"


def get_settings() -> Settings:
    """Return a fresh Settings instance reflecting current environment variables."""
    return Settings(
        app_host=os.getenv("APP_HOST", "127.0.0.1"),
        app_port=int(os.getenv("APP_PORT", "8000")),
        app_debug=_str_to_bool(os.getenv("APP_DEBUG", "false")),
        default_tenant_id=int(os.getenv("DEFAULT_TENANT_ID", "1")),
        default_associate_id=int(os.getenv("DEFAULT_ASSOCIATE_ID", "1")),
        default_associate_name=os.getenv("DEFAULT_ASSOCIATE_NAME", "Demo L1 Associate"),
        db_server=os.getenv("DB_SERVER", "localhost"),
        db_name=os.getenv("DB_NAME", "jotdesk"),
        db_schema=os.getenv("DB_SCHEMA", "dbo"),
        db_driver=os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
        db_auth_mode=os.getenv("DB_AUTH_MODE", "windows").strip().lower(),
        db_user=os.getenv("DB_USER", ""),
        db_password=os.getenv("DB_PASSWORD", ""),
        db_trust_server_certificate=os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes"),
        db_encrypt=os.getenv("DB_ENCRYPT", "yes"),
        db_timeout=int(os.getenv("DB_TIMEOUT", "10")),
        smtp_host=os.getenv("SMTP_HOST", "").strip(),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", "").strip(),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_use_tls=_str_to_bool(os.getenv("SMTP_USE_TLS", "true"), default=True),
        smtp_from_email=os.getenv("SMTP_FROM_EMAIL", "support@supportgenie.local").strip(),
        support_team_email=os.getenv("SUPPORT_TEAM_EMAIL", "support-team@supportgenie.local").strip(),
    )
