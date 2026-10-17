"""
Email repository mapped strictly to the existing JotDeskBuddy_Test schema:
- dbo.TicketEmailMessages (stores TicketId, MessageId, IsOutgoing, TenantId, AddedBy, AddedByName, AddedOnDate)
- dbo.Tickets (stores FromEmail, CCEmails, Subject, Description, ReportedMethodName='Email', IsDraft)
- dbo.Clients (stores ClientName, Email)

Schema Note:
JotDeskBuddy_Test does NOT contain a standalone Emails table for non-ticket emails, nor does
dbo.TicketEmailMessages contain columns for Subject, Body, To, CC, BCC, or Draft status.
Accordingly, this repository reads existing email message metadata joined with ticket context
and only inserts into dbo.TicketEmailMessages when a valid TicketId foreign key is present.
"""

from typing import Any, Dict, List, Optional

from supportgenie.database import DatabaseManager, db_manager


class EmailRepository:
    """Data access layer for ticket-linked email records in SQL Server."""

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        self.db = db or db_manager

    def list_email_records(
        self,
        folder: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve email records from dbo.TicketEmailMessages joined with dbo.Tickets and dbo.Clients.
        Supports filtering by folder ('inbox' -> IsOutgoing=0, 'sent' -> IsOutgoing=1, 'all' -> all)
        and searching across MessageId, Ticket Subject, Description, FromEmail, and ClientName.
        """
        where_clauses = ["1 = 1"]
        params: List[Any] = []

        normalized_folder = (folder or "all").strip().lower()
        if normalized_folder == "inbox":
            where_clauses.append("em.IsOutgoing = 0")
        elif normalized_folder == "sent":
            where_clauses.append("em.IsOutgoing = 1")

        if search and search.strip():
            term = f"%{search.strip()}%"
            where_clauses.append(
                "(em.MessageId LIKE ? OR t.Subject LIKE ? OR t.Description LIKE ? "
                "OR t.FromEmail LIKE ? OR t.ClientName LIKE ? OR em.AddedByName LIKE ?)"
            )
            params.extend([term, term, term, term, term, term])

        where_sql = " AND ".join(where_clauses)
        query = f"""
        SELECT
            em.Id AS EmailRecordId,
            em.TicketId,
            em.MessageId,
            em.IsOutgoing,
            CASE WHEN em.IsOutgoing = 1 THEN N'Sent' ELSE N'Inbox' END AS Folder,
            em.TenantId,
            em.AddedBy,
            em.AddedByName,
            em.AddedOnDate,
            t.Subject AS TicketSubject,
            t.Description AS TicketDescription,
            t.FromEmail AS ReporterEmail,
            t.CCEmails,
            t.ClientName,
            c.Email AS ClientEmail,
            t.TicketStatusName AS TicketStatus,
            t.TicketTypeName AS TicketCategory,
            t.TicketUrgencyName AS TicketPriority,
            t.PIC AS AssignedAssociate,
            t.TicketModuleName AS ModuleName,
            (
                SELECT TOP 1 tc.Chat
                FROM dbo.TicketChat tc
                WHERE tc.TicketId = t.Id
                ORDER BY tc.ChatRunningNumber ASC
            ) AS InitialChatSnippet
        FROM dbo.TicketEmailMessages em
        INNER JOIN dbo.Tickets t ON t.Id = em.TicketId
        LEFT JOIN dbo.Clients c ON c.Id = t.ClientId
        WHERE {where_sql}
        ORDER BY em.AddedOnDate DESC, em.Id DESC
        """
        return self.db.fetch_all(query, params)

    def list_email_reported_tickets(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve tickets from dbo.Tickets that were reported via Email (ReportedMethodName = 'Email')
        or have FromEmail populated, providing full visibility into email-originated support items.
        """
        where_clauses = [
            "t.IsDraft = 0",
            "(t.ReportedMethodName = N'Email' OR t.IsEmailImportCompleted = 1)",
        ]
        params: List[Any] = []

        if search and search.strip():
            term = f"%{search.strip()}%"
            where_clauses.append(
                "(t.Subject LIKE ? OR t.Description LIKE ? OR t.FromEmail LIKE ? OR t.ClientName LIKE ?)"
            )
            params.extend([term, term, term, term])

        where_sql = " AND ".join(where_clauses)
        query = f"""
        SELECT
            t.Id AS TicketId,
            t.Subject,
            t.Description,
            t.FromEmail,
            t.CCEmails,
            t.ClientName,
            t.TicketStatusName AS TicketStatus,
            t.TicketTypeName AS TicketCategory,
            t.TicketUrgencyName AS TicketPriority,
            t.PIC AS AssignedAssociate,
            t.ReportDate,
            t.AddedOnDate,
            t.IsEmailImportCompleted,
            t.SourceMessageId
        FROM dbo.Tickets t
        WHERE {where_sql}
        ORDER BY t.Id ASC
        """
        return self.db.fetch_all(query, params)

    def record_ticket_email_message(
        self,
        ticket_id: int,
        message_id: str,
        is_outgoing: bool,
        added_by: int = 201,
        added_by_name: str = "Demo L1 Associate",
    ) -> Optional[Dict[str, Any]]:
        """
        Persist an email message metadata reference in dbo.TicketEmailMessages for an existing TicketId.
        Because dbo.TicketEmailMessages has a non-null foreign key FK_TicketEmailMessages_Tickets,
        this is only supported when ticket_id references a valid row in dbo.Tickets.
        """
        ticket = self.db.fetch_one(
            "SELECT Id, TenantId FROM dbo.Tickets WHERE Id = ?",
            [ticket_id],
        )
        if not ticket:
            raise ValueError(f"Ticket #{ticket_id} does not exist; cannot link email record.")

        tenant_id = int(ticket.get("TenantId") or 1)
        insert_sql = """
        INSERT INTO dbo.TicketEmailMessages
            (TicketId, MessageId, IsOutgoing, TenantId, AddedBy, AddedByName, AddedOnDate)
        OUTPUT INSERTED.Id
        VALUES (?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
        """
        new_id = self.db.execute_write(
            insert_sql,
            [ticket_id, message_id, 1 if is_outgoing else 0, tenant_id, added_by, added_by_name],
            return_identity=True,
        )
        return {
            "email_record_id": new_id,
            "ticket_id": ticket_id,
            "message_id": message_id,
            "is_outgoing": bool(is_outgoing),
            "tenant_id": tenant_id,
            "added_by_name": added_by_name,
        }
