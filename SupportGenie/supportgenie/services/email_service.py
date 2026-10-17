"""
Email service for SupportGenie.
Handles:
1. Validating email recipient(s), CC, BCC, subject, and message body.
2. Sending emails via Python's smtplib when SMTP settings are configured in .env.
3. Explicitly reporting when SMTP is not configured (never simulating or faking email delivery).
4. Reading email metadata records from dbo.TicketEmailMessages (joined with dbo.Tickets)
   and recording outbound MessageId references when linked to an existing TicketId.
"""

from email.message import EmailMessage
from email.utils import make_msgid
import re
import smtplib
from typing import Any, Dict, List, Optional

from supportgenie.config import Settings, get_settings
from supportgenie.database import DatabaseError
from supportgenie.repositories.email_repository import EmailRepository

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailValidationError(ValueError):
    """Raised when an email composition payload fails validation."""


def validate_email_list(raw_emails: Optional[str], field_name: str, required: bool = False) -> List[str]:
    """Parse and validate a comma- or semicolon-separated list of email addresses."""
    if not raw_emails or not raw_emails.strip():
        if required:
            raise EmailValidationError(f"{field_name} is required.")
        return []

    parts = [p.strip() for p in re.split(r"[,;]+", raw_emails) if p.strip()]
    if required and not parts:
        raise EmailValidationError(f"{field_name} is required.")

    for addr in parts:
        if not EMAIL_REGEX.match(addr):
            raise EmailValidationError(f"Invalid email address in {field_name}: '{addr}'.")
    return parts


class EmailService:
    """Service layer for reading ticket-linked email records and sending support emails via SMTP."""

    def __init__(
        self,
        repository: Optional[EmailRepository] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.repository = repository or EmailRepository()
        self._settings = settings

    @property
    def settings(self) -> Settings:
        return self._settings or get_settings()

    def get_email_records(
        self,
        folder: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve available email records from SQL Server (dbo.TicketEmailMessages + dbo.Tickets)
        along with SMTP configuration status and schema capability metadata.
        """
        cfg = self.settings
        records = self.repository.list_email_records(folder=folder, search=search)
        email_tickets = self.repository.list_email_reported_tickets(search=search)

        inbox_count = sum(1 for r in records if not r.get("IsOutgoing"))
        sent_count = sum(1 for r in records if r.get("IsOutgoing"))

        return {
            "smtp_configured": cfg.is_smtp_configured,
            "support_team_email": cfg.support_team_email,
            "smtp_from_email": cfg.smtp_from_email,
            "schema_capabilities": {
                "table_name": "dbo.TicketEmailMessages",
                "stores_message_id_and_direction": True,
                "requires_ticket_id_foreign_key": True,
                "stores_standalone_email_body": False,
                "stores_standalone_drafts_in_db": False,
                "note": (
                    "dbo.TicketEmailMessages stores TicketId, MessageId, IsOutgoing, AddedByName, and AddedOnDate. "
                    "Subject, FromEmail, CCEmails, and Description are retrieved via its foreign key join to dbo.Tickets. "
                    "Standalone non-ticket email bodies and compose drafts are not stored in SQL Server without schema changes."
                ),
            },
            "counts": {
                "inbox": inbox_count,
                "sent": sent_count,
                "all": len(records),
                "email_reported_tickets": len(email_tickets),
            },
            "emails": records,
            "email_reported_tickets": email_tickets,
        }

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc_email: Optional[str] = None,
        bcc_email: Optional[str] = None,
        ticket_id: Optional[int] = None,
        record_in_db_if_ticket_linked: bool = True,
        added_by: Optional[int] = None,
        added_by_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate and send an email using SMTP if configured.
        Never simulates email sending when SMTP is unconfigured.
        Distinguishes clearly between:
        - sent via SMTP (`sent`: True/False)
        - recorded in dbo.TicketEmailMessages (`recorded_in_db`: True/False)
        """
        to_list = validate_email_list(to_email, "Recipient (To)", required=True)
        cc_list = validate_email_list(cc_email, "CC", required=False)
        bcc_list = validate_email_list(bcc_email, "BCC", required=False)

        clean_subject = (subject or "").strip()
        if not clean_subject:
            raise EmailValidationError("Subject is required.")
        if len(clean_subject) > 500:
            raise EmailValidationError("Subject cannot exceed 500 characters.")

        clean_body = (body or "").strip()
        if not clean_body:
            raise EmailValidationError("Message body is required.")

        cfg = self.settings
        eff_by = added_by if added_by is not None else cfg.default_associate_id
        eff_name = (added_by_name or cfg.default_associate_name).strip()

        generated_message_id = make_msgid(domain="supportgenie.local").strip("<>")
        smtp_sent = False
        smtp_error: Optional[str] = None

        if cfg.is_smtp_configured:
            msg = EmailMessage()
            msg["Subject"] = clean_subject
            msg["From"] = cfg.smtp_from_email
            msg["To"] = ", ".join(to_list)
            if cc_list:
                msg["Cc"] = ", ".join(cc_list)
            msg["Message-ID"] = f"<{generated_message_id}>"
            msg.set_content(clean_body)

            all_recipients = to_list + cc_list + bcc_list
            try:
                with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as server:
                    if cfg.smtp_use_tls:
                        server.starttls()
                    if cfg.smtp_username:
                        server.login(cfg.smtp_username, cfg.smtp_password)
                    server.send_message(msg, from_addr=cfg.smtp_from_email, to_addrs=all_recipients)
                smtp_sent = True
            except Exception as exc:
                smtp_error = f"SMTP delivery failed: {type(exc).__name__}."
        else:
            smtp_error = (
                "Email was NOT sent because SMTP is not configured in .env (SMTP_HOST is empty). "
                "SupportGenie does not simulate email delivery."
            )

        db_record: Optional[Dict[str, Any]] = None
        db_record_note: str = ""

        # Record outbound MessageId in dbo.TicketEmailMessages only when a valid ticket_id is supplied
        if ticket_id is not None and record_in_db_if_ticket_linked:
            if smtp_sent:
                try:
                    db_record = self.repository.record_ticket_email_message(
                        ticket_id=ticket_id,
                        message_id=generated_message_id,
                        is_outgoing=True,
                        added_by=eff_by,
                        added_by_name=eff_name,
                    )
                    db_record_note = (
                        f"Outbound MessageId '{generated_message_id}' recorded in dbo.TicketEmailMessages "
                        f"for Ticket #{ticket_id}."
                    )
                except (ValueError, DatabaseError) as exc:
                    db_record_note = f"Email sent via SMTP, but could not record metadata in dbo.TicketEmailMessages: {exc}"
            else:
                db_record_note = (
                    "No outbound record was inserted into dbo.TicketEmailMessages because the email was not sent."
                )
        elif ticket_id is None:
            db_record_note = (
                "Not recorded in dbo.TicketEmailMessages because no TicketId was linked "
                "(dbo.TicketEmailMessages requires a non-null TicketId foreign key and stores MessageId metadata only)."
            )

        if smtp_sent:
            status_summary = f"Email successfully sent via SMTP to {', '.join(to_list)}."
            if db_record:
                status_summary += f" {db_record_note}"
        else:
            status_summary = smtp_error or "Email could not be sent."

        return {
            "sent": smtp_sent,
            "smtp_configured": cfg.is_smtp_configured,
            "recorded_in_db": db_record is not None,
            "message_id": generated_message_id if smtp_sent else None,
            "ticket_id": ticket_id,
            "recipients": {
                "to": to_list,
                "cc": cc_list,
                "bcc": bcc_list,
            },
            "subject": clean_subject,
            "status_message": status_summary,
            "db_persistence_detail": db_record_note,
            "db_record": db_record,
        }
