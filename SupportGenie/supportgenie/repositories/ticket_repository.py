"""
Ticket repository mapped strictly to the existing JotDeskBuddy_Test SQL Server schema:
- dbo.Tickets
- dbo.Clients
- dbo.Projects
- dbo.Modules
- dbo.Pic
- dbo.ReportMethods
- dbo.ServiceLevelAgreements
- dbo.TicketChat
- dbo.TicketChatAttachments
- dbo.TicketFollowups
- dbo.FollowupAttachments
- dbo.TicketEmailMessages
- dbo.TicketFollowers
- dbo.UpdateLogs
- dbo.DeleteLogs
"""

import json
from typing import Any, Dict, List, Optional

from supportgenie.database import DatabaseManager, db_manager

# Mapping between human-readable TicketStatusName and integer TicketStatus in dbo.Tickets
STATUS_CODE_MAP: Dict[str, int] = {
    "Open": 1,
    "In Progress": 1,  # Seed data uses TicketStatus=1 with TicketStatusName='In Progress' (Ticket #9)
    "Closed": 2,
    "Resolved": 2,
}

# Mapping between TicketTypeName and integer TicketType in dbo.Tickets
CATEGORY_CODE_MAP: Dict[str, int] = {
    "Product Bug": 1,
    "Data Issue": 2,
    "Configuration Issue": 3,
    "Permission Issue": 4,
    "Integration Issue": 5,
    "Expected Behaviour": 3,
    "Change Request": 3,
    "Insufficient Information": 1,
}

URGENCY_CODE_MAP: Dict[str, int] = {
    "Critical": 1,
    "Urgent": 1,
    "High": 2,
    "Medium": 3,
    "Low": 4,
}


class TicketRepository:
    """Data access layer for support tickets and related records in SQL Server."""

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        self.db = db or db_manager

    def get_dashboard_counts(
        self,
        associate_id: Optional[int] = None,
        associate_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compute real ticket counts from dbo.Tickets (excluding drafts where IsDraft = 1).
        Uses TicketStatusName and TicketUrgencyName to match actual seed data conventions.
        """
        query = """
        SELECT
            COUNT(*) AS total_tickets,
            SUM(CASE WHEN t.TicketStatusName = N'Open' THEN 1 ELSE 0 END) AS open_tickets,
            SUM(CASE WHEN t.TicketStatusName = N'In Progress' THEN 1 ELSE 0 END) AS in_progress_tickets,
            SUM(CASE WHEN t.TicketStatusName IN (N'Closed', N'Resolved') OR t.TicketStatus = 2 THEN 1 ELSE 0 END) AS resolved_tickets,
            SUM(CASE WHEN t.TicketUrgencyName IN (N'High', N'Urgent', N'Critical') OR t.TicketUrgency IN (1, 2) THEN 1 ELSE 0 END) AS high_priority_tickets,
            SUM(
                CASE
                    WHEN (? IS NOT NULL AND t.PICId = ?)
                      OR (? IS NOT NULL AND t.PIC = ?)
                    THEN 1 ELSE 0
                END
            ) AS assigned_to_associate
        FROM dbo.Tickets t
        WHERE t.IsDraft = 0
        """
        params = [associate_id, associate_id, associate_name, associate_name]
        row = self.db.fetch_one(query, params) or {}
        return {
            "total_tickets": int(row.get("total_tickets") or 0),
            "open_tickets": int(row.get("open_tickets") or 0),
            "in_progress_tickets": int(row.get("in_progress_tickets") or 0),
            "resolved_tickets": int(row.get("resolved_tickets") or 0),
            "high_priority_tickets": int(row.get("high_priority_tickets") or 0),
            "assigned_to_associate": int(row.get("assigned_to_associate") or 0),
            "current_associate_id": associate_id,
            "current_associate_name": associate_name,
        }

    def get_filter_metadata(self) -> Dict[str, Any]:
        """Retrieve actual reference data from dbo.Pic, dbo.Clients, dbo.Modules, and dbo.Tickets."""
        associates = self.db.fetch_all(
            "SELECT Id, Name, Email, TenantId FROM dbo.Pic ORDER BY Id ASC"
        )
        clients = self.db.fetch_all(
            "SELECT Id, ClientName, Email, ClientShortCode, TenantId FROM dbo.Clients ORDER BY ClientName ASC"
        )
        modules = self.db.fetch_all(
            "SELECT Id, ProjectId, Name, ProjectName, TenantId FROM dbo.Modules ORDER BY ProjectName ASC, Name ASC"
        )
        statuses_rows = self.db.fetch_all(
            "SELECT DISTINCT TicketStatusName FROM dbo.Tickets WHERE IsDraft = 0 AND TicketStatusName IS NOT NULL ORDER BY TicketStatusName ASC"
        )
        categories_rows = self.db.fetch_all(
            "SELECT DISTINCT TicketTypeName FROM dbo.Tickets WHERE IsDraft = 0 AND TicketTypeName IS NOT NULL ORDER BY TicketTypeName ASC"
        )
        priorities_rows = self.db.fetch_all(
            "SELECT DISTINCT TicketUrgencyName FROM dbo.Tickets WHERE IsDraft = 0 AND TicketUrgencyName IS NOT NULL ORDER BY TicketUrgencyName ASC"
        )

        statuses = [r["TicketStatusName"] for r in statuses_rows if r.get("TicketStatusName")]
        for std_status in ["Open", "In Progress", "Closed"]:
            if std_status not in statuses:
                statuses.append(std_status)

        categories = [r["TicketTypeName"] for r in categories_rows if r.get("TicketTypeName")]
        for std_cat in CATEGORY_CODE_MAP:
            if std_cat not in categories:
                categories.append(std_cat)

        priorities = [r["TicketUrgencyName"] for r in priorities_rows if r.get("TicketUrgencyName")]
        for std_prio in ["High", "Medium", "Low"]:
            if std_prio not in priorities:
                priorities.append(std_prio)

        return {
            "associates": associates,
            "clients": clients,
            "modules": modules,
            "statuses": statuses,
            "categories": categories,
            "priorities": priorities,
        }

    def list_tickets(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_pic: Optional[str] = None,
        client_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve non-draft tickets from dbo.Tickets with optional parameterized search and filters.
        """
        where_clauses = ["t.IsDraft = 0"]
        params: List[Any] = []

        if search and search.strip():
            term = f"%{search.strip()}%"
            where_clauses.append(
                "(CAST(t.Id AS NVARCHAR(50)) LIKE ? OR t.Subject LIKE ? OR t.Description LIKE ? OR t.ClientName LIKE ?)"
            )
            params.extend([term, term, term, term])

        if status and status.strip():
            where_clauses.append("t.TicketStatusName = ?")
            params.append(status.strip())

        if category and category.strip():
            where_clauses.append("t.TicketTypeName = ?")
            params.append(category.strip())

        if priority and priority.strip():
            where_clauses.append("t.TicketUrgencyName = ?")
            params.append(priority.strip())

        if assigned_pic and assigned_pic.strip():
            val = assigned_pic.strip()
            where_clauses.append("(t.PIC = ? OR CAST(t.PICId AS NVARCHAR(50)) = ?)")
            params.extend([val, val])

        if client_id is not None:
            where_clauses.append("t.ClientId = ?")
            params.append(client_id)

        where_sql = " AND ".join(where_clauses)
        query = f"""
        SELECT
            t.Id AS TicketId,
            t.Subject,
            t.Description,
            t.TicketType,
            t.TicketTypeName AS Category,
            t.TicketUrgency,
            t.TicketUrgencyName AS Priority,
            t.TicketStatus,
            t.TicketStatusName AS Status,
            t.ClientId,
            t.ClientName,
            t.PICId,
            t.PIC AS AssignedAssociate,
            t.TicketModule AS ModuleId,
            t.TicketModuleName AS ModuleName,
            t.ProjectId,
            t.ProjectName,
            t.ReportedMethodId,
            t.ReportedMethodName,
            t.FromEmail,
            t.CCEmails,
            t.Remark,
            t.ClosedOn,
            t.ClosedBy,
            t.HoursSpentToClose,
            t.IsClosedWithinSLA,
            t.TenantId,
            t.AddedBy,
            t.AddedByName,
            t.ReportDate,
            t.AddedOnDate AS CreatedDate,
            t.EditedOnDate AS UpdatedDate,
            (SELECT COUNT(*) FROM dbo.TicketChat c WHERE c.TicketId = t.Id) AS ChatCount,
            (SELECT COUNT(*) FROM dbo.TicketFollowups f WHERE f.TicketId = t.Id) AS FollowupCount
        FROM dbo.Tickets t
        WHERE {where_sql}
        ORDER BY t.Id ASC
        """
        return self.db.fetch_all(query, params)

    def get_ticket_by_id(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single ticket and its joined client, associate, module, project, and SLA context."""
        query = """
        SELECT
            t.Id AS TicketId,
            t.Subject,
            t.Description,
            t.TicketType,
            t.TicketTypeName AS Category,
            t.TicketUrgency,
            t.TicketUrgencyName AS Priority,
            t.TicketStatus,
            t.TicketStatusName AS Status,
            t.ClientId,
            t.ClientName,
            c.Email AS ClientEmail,
            c.ClientShortCode,
            t.PICId,
            t.PIC AS AssignedAssociate,
            p.Email AS AssociateEmail,
            t.TicketModule AS ModuleId,
            t.TicketModuleName AS ModuleName,
            t.ProjectId,
            t.ProjectName,
            t.ReportedMethodId,
            t.ReportedMethodName,
            t.FromEmail,
            t.CCEmails,
            t.Remark,
            t.ClosedOn,
            t.ClosedBy,
            t.HoursSpentToClose,
            t.IsClosedWithinSLA,
            t.IsEmailImportCompleted,
            t.SourceMessageId,
            t.TenantId,
            t.AddedBy,
            t.AddedByName,
            t.EditedBy,
            t.EditedByName,
            t.ReportDate,
            t.AddedOnDate AS CreatedDate,
            t.EditedOnDate AS UpdatedDate,
            sla.Hours AS SLAHours,
            sla.ExcludeSundays AS SLAExcludeSundays,
            sla.ExcludePublicHolidays AS SLAExcludePublicHolidays
        FROM dbo.Tickets t
        LEFT JOIN dbo.Clients c ON c.Id = t.ClientId
        LEFT JOIN dbo.Pic p ON p.Id = t.PICId
        LEFT JOIN dbo.ServiceLevelAgreements sla
            ON sla.ClientId = t.ClientId AND sla.TicketType = t.TicketType
        WHERE t.Id = ?
        """
        ticket = self.db.fetch_one(query, [ticket_id])
        if not ticket:
            return None

        followers = self.db.fetch_all(
            """
            SELECT Id, TicketId, UserId, UserName, AddedByName, AddedOnDate
            FROM dbo.TicketFollowers
            WHERE TicketId = ?
            ORDER BY Id ASC
            """,
            [ticket_id],
        )
        ticket["Followers"] = followers
        return ticket

    def get_ticket_history(self, ticket_id: int) -> Dict[str, Any]:
        """
        Retrieve complete communication, internal follow-ups, attachments, and update audit logs
        for a specific ticket from SQL Server.
        """
        chats = self.db.fetch_all(
            """
            SELECT
                c.Id,
                c.TicketId,
                c.ChatRunningNumber,
                c.Chat,
                c.TenantId,
                c.AddedBy,
                c.AddedByName,
                c.AddedOnDate,
                c.EditedOnDate
            FROM dbo.TicketChat c
            WHERE c.TicketId = ?
            ORDER BY c.ChatRunningNumber ASC, c.AddedOnDate ASC
            """,
            [ticket_id],
        )

        chat_attachments = self.db.fetch_all(
            """
            SELECT
                ca.Id,
                ca.ChatId,
                ca.AttachmentName,
                ca.AttachmentSize,
                ca.AttachmentPath,
                ca.AddedByName,
                ca.AddedOnDate
            FROM dbo.TicketChatAttachments ca
            INNER JOIN dbo.TicketChat c ON c.Id = ca.ChatId
            WHERE c.TicketId = ?
            ORDER BY ca.Id ASC
            """,
            [ticket_id],
        )

        followups = self.db.fetch_all(
            """
            SELECT
                f.Id,
                f.TicketId,
                f.FollowupRunningNumber,
                f.Remarks,
                f.TenantId,
                f.AddedBy,
                f.AddedByName,
                f.AddedOnDate,
                f.EditedOnDate,
                f.IsEmailImportCompleted,
                f.SourceMessageId
            FROM dbo.TicketFollowups f
            WHERE f.TicketId = ?
            ORDER BY f.FollowupRunningNumber ASC, f.AddedOnDate ASC
            """,
            [ticket_id],
        )

        followup_attachments = self.db.fetch_all(
            """
            SELECT
                fa.Id,
                fa.FollowupId,
                fa.AttachmentName,
                fa.AttachmentSize,
                fa.AttachmentPath,
                fa.AddedByName,
                fa.AddedOnDate
            FROM dbo.FollowupAttachments fa
            INNER JOIN dbo.TicketFollowups f ON f.Id = fa.FollowupId
            WHERE f.TicketId = ?
            ORDER BY fa.Id ASC
            """,
            [ticket_id],
        )

        email_messages = self.db.fetch_all(
            """
            SELECT
                em.Id,
                em.TicketId,
                em.MessageId,
                em.IsOutgoing,
                em.TenantId,
                em.AddedBy,
                em.AddedByName,
                em.AddedOnDate
            FROM dbo.TicketEmailMessages em
            WHERE em.TicketId = ?
            ORDER BY em.AddedOnDate ASC, em.Id ASC
            """,
            [ticket_id],
        )

        update_logs = self.db.fetch_all(
            """
            SELECT
                u.Id,
                u.EntityName,
                u.PrimaryKey,
                u.Data,
                u.UpdatedOnDate,
                u.UpdatedBy,
                u.UpdatedByName,
                u.TenantId
            FROM dbo.UpdateLogs u
            WHERE u.EntityName = N'Tickets' AND u.PrimaryKey = ?
            ORDER BY u.UpdatedOnDate DESC, u.Id DESC
            """,
            [ticket_id],
        )

        # Attach attachments directly to their parent chat/followup items for convenience
        chat_att_by_id: Dict[int, List[Dict[str, Any]]] = {}
        for att in chat_attachments:
            cid = int(att["ChatId"])
            chat_att_by_id.setdefault(cid, []).append(att)
        for chat in chats:
            chat["Attachments"] = chat_att_by_id.get(int(chat["Id"]), [])

        followup_att_by_id: Dict[int, List[Dict[str, Any]]] = {}
        for att in followup_attachments:
            fid = int(att["FollowupId"])
            followup_att_by_id.setdefault(fid, []).append(att)
        for fup in followups:
            fup["Attachments"] = followup_att_by_id.get(int(fup["Id"]), [])

        return {
            "ticket_id": ticket_id,
            "chats": chats,
            "followups": followups,
            "email_messages": email_messages,
            "update_logs": update_logs,
        }

    def add_comment_or_note(
        self,
        ticket_id: int,
        text: str,
        note_type: str = "followup",
        added_by: int = 201,
        added_by_name: str = "Demo L1 Associate",
    ) -> Dict[str, Any]:
        """
        Persist an internal note (dbo.TicketFollowups) or chat reply (dbo.TicketChat)
        to SQL Server using parameterized queries.
        """
        ticket = self.get_ticket_by_id(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket #{ticket_id} does not exist.")

        tenant_id = int(ticket.get("TenantId") or 1)
        normalized_type = (note_type or "followup").strip().lower()

        if normalized_type == "chat":
            next_num_row = self.db.fetch_one(
                "SELECT ISNULL(MAX(ChatRunningNumber), 0) + 1 AS NextNum FROM dbo.TicketChat WHERE TicketId = ?",
                [ticket_id],
            )
            next_num = int((next_num_row or {}).get("NextNum") or 1)
            insert_sql = """
            INSERT INTO dbo.TicketChat
                (TicketId, ChatRunningNumber, Chat, TenantId, AddedBy, AddedByName, AddedOnDate)
            OUTPUT INSERTED.Id
            VALUES (?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
            """
            new_id = self.db.execute_write(
                insert_sql,
                [ticket_id, next_num, text.strip(), tenant_id, added_by, added_by_name],
                return_identity=True,
            )
            self.db.execute_write(
                "UPDATE dbo.Tickets SET EditedBy = ?, EditedByName = ?, EditedOnDate = SYSUTCDATETIME() WHERE Id = ?",
                [added_by, added_by_name, ticket_id],
            )
            return {
                "id": new_id,
                "ticket_id": ticket_id,
                "note_type": "chat",
                "running_number": next_num,
                "text": text.strip(),
                "added_by_name": added_by_name,
            }

        # Default: internal follow-up note in dbo.TicketFollowups
        next_num_row = self.db.fetch_one(
            "SELECT ISNULL(MAX(FollowupRunningNumber), 0) + 1 AS NextNum FROM dbo.TicketFollowups WHERE TicketId = ?",
            [ticket_id],
        )
        next_num = int((next_num_row or {}).get("NextNum") or 1)
        insert_sql = """
        INSERT INTO dbo.TicketFollowups
            (TicketId, FollowupRunningNumber, Remarks, TenantId, AddedBy, AddedByName, AddedOnDate, IsEmailImportCompleted)
        OUTPUT INSERTED.Id
        VALUES (?, ?, ?, ?, ?, ?, SYSUTCDATETIME(), 0)
        """
        new_id = self.db.execute_write(
            insert_sql,
            [ticket_id, next_num, text.strip(), tenant_id, added_by, added_by_name],
            return_identity=True,
        )
        self.db.execute_write(
            "UPDATE dbo.Tickets SET EditedBy = ?, EditedByName = ?, EditedOnDate = SYSUTCDATETIME() WHERE Id = ?",
            [added_by, added_by_name, ticket_id],
        )
        return {
            "id": new_id,
            "ticket_id": ticket_id,
            "note_type": "followup",
            "running_number": next_num,
            "text": text.strip(),
            "added_by_name": added_by_name,
        }

    def update_ticket(
        self,
        ticket_id: int,
        status_name: Optional[str] = None,
        pic_id: Optional[int] = None,
        remark: Optional[str] = None,
        category_name: Optional[str] = None,
        priority_name: Optional[str] = None,
        hours_spent: Optional[float] = None,
        updated_by: int = 201,
        updated_by_name: str = "Demo L1 Associate",
    ) -> Dict[str, Any]:
        """
        Update supported fields on dbo.Tickets (status, assigned associate/PIC, resolution remark,
        category, priority) and record an audit entry in dbo.UpdateLogs.
        """
        ticket = self.get_ticket_by_id(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket #{ticket_id} does not exist.")

        tenant_id = int(ticket.get("TenantId") or 1)
        set_clauses: List[str] = [
            "EditedBy = ?",
            "EditedByName = ?",
            "EditedOnDate = SYSUTCDATETIME()",
        ]
        params: List[Any] = [updated_by, updated_by_name]
        audit_changes: Dict[str, Any] = {}

        if status_name and status_name.strip():
            clean_status = status_name.strip()
            status_code = STATUS_CODE_MAP.get(clean_status, 1)
            set_clauses.append("TicketStatus = ?")
            params.append(status_code)
            set_clauses.append("TicketStatusName = ?")
            params.append(clean_status)
            audit_changes["TicketStatusName"] = clean_status

            if clean_status in {"Closed", "Resolved"}:
                set_clauses.append("ClosedOn = SYSUTCDATETIME()")
                set_clauses.append("ClosedBy = ?")
                params.append(updated_by_name)
                if hours_spent is not None and hours_spent >= 0:
                    set_clauses.append("HoursSpentToClose = ?")
                    params.append(float(hours_spent))
                    sla_hours = float(ticket.get("SLAHours") or 24.0)
                    within_sla = 1 if float(hours_spent) <= sla_hours else 0
                    set_clauses.append("IsClosedWithinSLA = ?")
                    params.append(within_sla)

        if pic_id is not None:
            pic_row = self.db.fetch_one("SELECT Id, Name FROM dbo.Pic WHERE Id = ?", [pic_id])
            if not pic_row:
                raise ValueError(f"Support associate (PIC Id={pic_id}) does not exist in dbo.Pic.")
            set_clauses.append("PICId = ?")
            params.append(int(pic_row["Id"]))
            set_clauses.append("PIC = ?")
            params.append(pic_row["Name"])
            audit_changes["PIC"] = pic_row["Name"]
            audit_changes["PICId"] = int(pic_row["Id"])

        if remark is not None:
            clean_remark = remark.strip()
            set_clauses.append("Remark = ?")
            params.append(clean_remark if clean_remark else None)
            audit_changes["Remark"] = clean_remark

        if category_name and category_name.strip():
            clean_cat = category_name.strip()
            cat_code = CATEGORY_CODE_MAP.get(clean_cat, int(ticket.get("TicketType") or 1))
            set_clauses.append("TicketType = ?")
            params.append(cat_code)
            set_clauses.append("TicketTypeName = ?")
            params.append(clean_cat)
            audit_changes["TicketTypeName"] = clean_cat

        if priority_name and priority_name.strip():
            clean_prio = priority_name.strip()
            prio_code = URGENCY_CODE_MAP.get(clean_prio, int(ticket.get("TicketUrgency") or 3))
            set_clauses.append("TicketUrgency = ?")
            params.append(prio_code)
            set_clauses.append("TicketUrgencyName = ?")
            params.append(clean_prio)
            audit_changes["TicketUrgencyName"] = clean_prio

        update_sql = f"UPDATE dbo.Tickets SET {', '.join(set_clauses)} WHERE Id = ?"
        params.append(ticket_id)

        audit_sql = """
        INSERT INTO dbo.UpdateLogs (EntityName, PrimaryKey, Data, UpdatedOnDate, UpdatedBy, UpdatedByName, TenantId)
        VALUES (N'Tickets', ?, ?, SYSUTCDATETIME(), ?, ?, ?)
        """
        audit_params = [
            ticket_id,
            json.dumps(audit_changes, ensure_ascii=False),
            updated_by,
            updated_by_name,
            tenant_id,
        ]

        self.db.execute_transaction(
            [
                (update_sql, params),
                (audit_sql, audit_params),
            ]
        )

        return self.get_ticket_by_id(ticket_id) or {"TicketId": ticket_id}

    def get_historical_tickets_for_nlp(self, exclude_ticket_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve historical tickets along with their latest follow-up remarks and resolution remarks
        to support historical ticket assistance in the NLP engine.
        """
        query = """
        SELECT
            t.Id AS TicketId,
            t.Subject,
            t.Description,
            t.TicketTypeName AS Category,
            t.TicketStatusName AS Status,
            t.TicketUrgencyName AS Priority,
            t.TicketModuleName AS ModuleName,
            t.ProjectName,
            t.ClientName,
            t.Remark AS ResolutionRemark,
            (
                SELECT TOP 1 f.Remarks
                FROM dbo.TicketFollowups f
                WHERE f.TicketId = t.Id
                ORDER BY f.FollowupRunningNumber DESC, f.Id DESC
            ) AS LatestFollowup,
            (
                SELECT TOP 1 c.Chat
                FROM dbo.TicketChat c
                WHERE c.TicketId = t.Id
                ORDER BY c.ChatRunningNumber DESC, c.Id DESC
            ) AS LatestChat
        FROM dbo.Tickets t
        WHERE t.IsDraft = 0
          AND (? IS NULL OR t.Id <> ?)
        ORDER BY t.Id ASC
        """
        return self.db.fetch_all(query, [exclude_ticket_id, exclude_ticket_id])
