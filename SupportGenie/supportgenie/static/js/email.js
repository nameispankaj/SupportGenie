/**
 * SupportGenie — Gmail-Inspired Email Console Script (email.js)
 * Connects to /api/emails and /api/emails/send.
 * Clearly distinguishes between emails genuinely sent via SMTP vs. unconfigured SMTP
 * and vs. metadata recorded in dbo.TicketEmailMessages.
 */

(function () {
    "use strict";

    const DRAFTS_STORAGE_KEY = "supportgenie_local_email_drafts_v1";

    let currentFolder = "inbox";
    let emailRecords = [];
    let emailReportedTickets = [];
    let selectedItemKey = null;
    let configuredSupportEmail = "support-team@supportgenie.local";

    const dom = {
        dbBadge: document.getElementById("dbConnectionBadge"),
        dbText: document.getElementById("dbConnectionText"),
        globalAssociateSelect: document.getElementById("globalAssociateSelect"),

        openComposeBtn: document.getElementById("openComposeBtn"),
        folderButtons: document.querySelectorAll(".folder-btn"),
        folderCountInbox: document.getElementById("folderCountInbox"),
        folderCountSent: document.getElementById("folderCountSent"),
        folderCountAll: document.getElementById("folderCountAll"),
        folderCountReported: document.getElementById("folderCountReported"),
        folderCountDrafts: document.getElementById("folderCountDrafts"),

        smtpStatusText: document.getElementById("smtpStatusText"),
        configuredSupportEmailEl: document.getElementById("configuredSupportEmail"),
        emailTransportBanner: document.getElementById("emailTransportBanner"),

        emailSearchInput: document.getElementById("emailSearchInput"),
        refreshEmailsBtn: document.getElementById("refreshEmailsBtn"),
        emailListContainer: document.getElementById("emailListContainer"),

        noEmailSelectedView: document.getElementById("noEmailSelectedView"),
        emailDetailView: document.getElementById("emailDetailView"),
        emailDetailFolderBadge: document.getElementById("emailDetailFolderBadge"),
        emailDetailTicketChip: document.getElementById("emailDetailTicketChip"),
        emailDetailSubject: document.getElementById("emailDetailSubject"),
        emailDetailMessageId: document.getElementById("emailDetailMessageId"),
        emailDetailAddedBy: document.getElementById("emailDetailAddedBy"),
        emailDetailFrom: document.getElementById("emailDetailFrom"),
        emailDetailCC: document.getElementById("emailDetailCC"),
        emailDetailClient: document.getElementById("emailDetailClient"),
        emailDetailDate: document.getElementById("emailDetailDate"),
        emailDetailDescription: document.getElementById("emailDetailDescription"),
        emailDetailChatBox: document.getElementById("emailDetailChatBox"),
        emailDetailChatSnippet: document.getElementById("emailDetailChatSnippet"),
        replyToEmailBtn: document.getElementById("replyToEmailBtn"),
        openTicketInSupportLink: document.getElementById("openTicketInSupportLink"),

        composeModal: document.getElementById("composeModal"),
        closeComposeBtn: document.getElementById("closeComposeBtn"),
        composeEmailForm: document.getElementById("composeEmailForm"),
        composeTo: document.getElementById("composeTo"),
        composeCc: document.getElementById("composeCc"),
        composeBcc: document.getElementById("composeBcc"),
        composeTicketId: document.getElementById("composeTicketId"),
        composeSubject: document.getElementById("composeSubject"),
        composeBody: document.getElementById("composeBody"),
        fillSupportTeamBtn: document.getElementById("fillSupportTeamBtn"),
        sendEmailSubmitBtn: document.getElementById("sendEmailSubmitBtn"),
        saveDraftBtn: document.getElementById("saveDraftBtn"),
        discardComposeBtn: document.getElementById("discardComposeBtn"),
        composeResultFeedback: document.getElementById("composeResultFeedback"),
    };

    function escapeHtml(value) {
        if (value === null || value === undefined) return "";
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function formatDate(isoStr) {
        if (!isoStr) return "N/A";
        const d = new Date(isoStr);
        if (Number.isNaN(d.getTime())) return String(isoStr);
        return d.toISOString().replace("T", " ").substring(0, 19) + " UTC";
    }

    function getLocalDrafts() {
        try {
            const raw = localStorage.getItem(DRAFTS_STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (err) {
            return [];
        }
    }

    function saveLocalDrafts(drafts) {
        try {
            localStorage.setItem(DRAFTS_STORAGE_KEY, JSON.stringify(drafts));
        } catch (err) {
            // Ignore storage quota errors
        }
        dom.folderCountDrafts.textContent = getLocalDrafts().length;
    }

    async function checkDatabaseHealth() {
        try {
            const resp = await fetch("/health/db");
            const data = await resp.json();
            if (resp.ok && data.connected) {
                dom.dbBadge.className = "status-pill status-ok";
                dom.dbText.textContent = "SQL Server: " + (data.database || "Connected");
            } else {
                dom.dbBadge.className = "status-pill status-error";
                dom.dbText.textContent = "DB Disconnected";
            }
        } catch (err) {
            dom.dbBadge.className = "status-pill status-error";
            dom.dbText.textContent = "DB Unreachable";
        }
    }

    async function loadEmails() {
        dom.emailListContainer.innerHTML = `<div class="empty-cell">Loading email records from SQL Server...</div>`;
        const search = dom.emailSearchInput.value.trim();
        const params = new URLSearchParams({ folder: "all" });
        if (search) params.set("search", search);

        try {
            const resp = await fetch(`/api/emails?${params.toString()}`);
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || "Failed to load email records from SQL Server.");
            }

            emailRecords = data.emails || [];
            emailReportedTickets = data.email_reported_tickets || [];
            configuredSupportEmail = data.support_team_email || configuredSupportEmail;
            dom.configuredSupportEmailEl.textContent = configuredSupportEmail;

            const counts = data.counts || {};
            dom.folderCountInbox.textContent = counts.inbox ?? 0;
            dom.folderCountSent.textContent = counts.sent ?? 0;
            dom.folderCountAll.textContent = counts.all ?? 0;
            dom.folderCountReported.textContent = counts.email_reported_tickets ?? 0;
            dom.folderCountDrafts.textContent = getLocalDrafts().length;

            if (data.smtp_configured) {
                dom.smtpStatusText.textContent = "Configured (Active)";
                dom.smtpStatusText.style.color = "var(--success)";
                dom.emailTransportBanner.className = "state-banner banner-info";
                dom.emailTransportBanner.textContent =
                    "SMTP transport is configured. Emails sent from Compose will be delivered via SMTP and linked to dbo.TicketEmailMessages when a Ticket ID is supplied.";
            } else {
                dom.smtpStatusText.textContent = "Not Configured (.env)";
                dom.smtpStatusText.style.color = "var(--warning)";
                dom.emailTransportBanner.className = "state-banner banner-warning";
                dom.emailTransportBanner.textContent =
                    "SMTP is not configured in .env (SMTP_HOST is empty). You can inspect SQL Server email records and test the Compose validation workflow, but SupportGenie will accurately report that email sending is not configured rather than faking delivery.";
            }

            renderFolderList();
        } catch (err) {
            dom.emailListContainer.innerHTML = `<div class="empty-cell">${escapeHtml(err.message)}</div>`;
            dom.emailTransportBanner.className = "state-banner banner-error";
            dom.emailTransportBanner.textContent = err.message;
        }
    }

    function getFilteredItemsForCurrentFolder() {
        if (currentFolder === "inbox") {
            return emailRecords.filter((r) => !r.IsOutgoing).map((r) => ({ type: "record", data: r }));
        }
        if (currentFolder === "sent") {
            return emailRecords.filter((r) => Boolean(r.IsOutgoing)).map((r) => ({ type: "record", data: r }));
        }
        if (currentFolder === "all") {
            return emailRecords.map((r) => ({ type: "record", data: r }));
        }
        if (currentFolder === "email_tickets") {
            return emailReportedTickets.map((t) => ({ type: "ticket", data: t }));
        }
        if (currentFolder === "drafts") {
            return getLocalDrafts().map((d) => ({ type: "draft", data: d }));
        }
        return [];
    }

    function renderFolderList() {
        const items = getFilteredItemsForCurrentFolder();
        if (!items.length) {
            dom.emailListContainer.innerHTML = `<div class="empty-cell">No records in this folder matching your search.</div>`;
            return;
        }

        dom.emailListContainer.innerHTML = items
            .map((item, idx) => {
                if (item.type === "record") {
                    const r = item.data;
                    const key = `rec-${r.EmailRecordId}`;
                    const isSel = key === selectedItemKey;
                    const badgeClass = r.IsOutgoing ? "badge badge-closed" : "badge badge-open";
                    return `
                        <div class="email-row ${isSel ? "selected-row" : ""}" data-idx="${idx}" data-key="${escapeHtml(key)}">
                            <div class="email-row-top">
                                <span><span class="${badgeClass}">${r.IsOutgoing ? "Sent" : "Inbox"}</span> &bull; ${escapeHtml(r.AddedByName)}</span>
                                <span>${escapeHtml(formatDate(r.AddedOnDate).substring(0, 16))}</span>
                            </div>
                            <div class="email-row-subject">[Ticket #${escapeHtml(r.TicketId)}] ${escapeHtml(r.TicketSubject)}</div>
                            <div class="email-row-snippet">MessageId: ${escapeHtml(r.MessageId)} &mdash; ${escapeHtml(r.TicketDescription)}</div>
                        </div>
                    `;
                }
                if (item.type === "ticket") {
                    const t = item.data;
                    const key = `tkt-${t.TicketId}`;
                    const isSel = key === selectedItemKey;
                    return `
                        <div class="email-row ${isSel ? "selected-row" : ""}" data-idx="${idx}" data-key="${escapeHtml(key)}">
                            <div class="email-row-top">
                                <span><span class="badge badge-category">Reported via Email</span> &bull; ${escapeHtml(t.FromEmail || t.ClientName)}</span>
                                <span>${escapeHtml(formatDate(t.ReportDate || t.AddedOnDate).substring(0, 16))}</span>
                            </div>
                            <div class="email-row-subject">[Ticket #${escapeHtml(t.TicketId)}] ${escapeHtml(t.Subject)}</div>
                            <div class="email-row-snippet">${escapeHtml(t.Description)}</div>
                        </div>
                    `;
                }
                const d = item.data;
                const key = `drf-${d.id}`;
                const isSel = key === selectedItemKey;
                return `
                    <div class="email-row ${isSel ? "selected-row" : ""}" data-idx="${idx}" data-key="${escapeHtml(key)}">
                        <div class="email-row-top">
                            <span><span class="badge badge-progress">Local Draft</span> &bull; To: ${escapeHtml(d.to)}</span>
                            <span>${escapeHtml(formatDate(d.saved_at).substring(0, 16))}</span>
                        </div>
                        <div class="email-row-subject">${escapeHtml(d.subject || "(No subject)")}</div>
                        <div class="email-row-snippet">${escapeHtml(d.body || "")}</div>
                    </div>
                `;
            })
            .join("");

        Array.from(dom.emailListContainer.querySelectorAll(".email-row")).forEach((row) => {
            row.addEventListener("click", () => {
                const idx = Number(row.dataset.idx);
                selectedItemKey = row.dataset.key;
                renderFolderList();
                showItemDetail(items[idx]);
            });
        });
    }

    function showItemDetail(item) {
        if (!item) return;

        if (item.type === "draft") {
            const d = item.data;
            openComposeDrawer({
                to: d.to,
                cc: d.cc,
                bcc: d.bcc,
                ticket_id: d.ticket_id,
                subject: d.subject,
                body: d.body,
            });
            return;
        }

        dom.noEmailSelectedView.classList.add("hidden");
        dom.emailDetailView.classList.remove("hidden");

        if (item.type === "record") {
            const r = item.data;
            dom.emailDetailFolderBadge.className = r.IsOutgoing ? "badge badge-closed" : "badge badge-open";
            dom.emailDetailFolderBadge.textContent = r.IsOutgoing ? "Sent (IsOutgoing = 1)" : "Inbox (IsOutgoing = 0)";
            dom.emailDetailTicketChip.textContent = `Ticket #${r.TicketId}`;
            dom.emailDetailSubject.textContent = r.TicketSubject;
            dom.emailDetailMessageId.textContent = r.MessageId;
            dom.emailDetailAddedBy.textContent = r.AddedByName;
            dom.emailDetailFrom.textContent = r.ReporterEmail || r.ClientEmail || "N/A";
            dom.emailDetailCC.textContent = r.CCEmails || "None";
            dom.emailDetailClient.textContent = `${r.ClientName} (${r.TicketStatus})`;
            dom.emailDetailDate.textContent = formatDate(r.AddedOnDate);
            dom.emailDetailDescription.textContent = r.TicketDescription;

            if (r.InitialChatSnippet) {
                dom.emailDetailChatBox.classList.remove("hidden");
                dom.emailDetailChatSnippet.textContent = r.InitialChatSnippet;
            } else {
                dom.emailDetailChatBox.classList.add("hidden");
            }

            dom.openTicketInSupportLink.href = `/support?ticket_id=${encodeURIComponent(r.TicketId)}`;
            dom.replyToEmailBtn.onclick = () => {
                openComposeDrawer({
                    to: r.ReporterEmail || r.ClientEmail || configuredSupportEmail,
                    cc: r.CCEmails || "",
                    ticket_id: r.TicketId,
                    subject: `Re: [Ticket #${r.TicketId}] ${r.TicketSubject}`,
                    body: `\n\n--- Regarding Ticket #${r.TicketId} (MessageId: ${r.MessageId}) ---\n${r.TicketDescription}`,
                });
            };
        } else if (item.type === "ticket") {
            const t = item.data;
            dom.emailDetailFolderBadge.className = "badge badge-category";
            dom.emailDetailFolderBadge.textContent = "Email-Reported Ticket";
            dom.emailDetailTicketChip.textContent = `Ticket #${t.TicketId}`;
            dom.emailDetailSubject.textContent = t.Subject;
            dom.emailDetailMessageId.textContent = t.SourceMessageId || "N/A (dbo.Tickets record)";
            dom.emailDetailAddedBy.textContent = t.AssignedAssociate || "Unassigned";
            dom.emailDetailFrom.textContent = t.FromEmail || "N/A";
            dom.emailDetailCC.textContent = t.CCEmails || "None";
            dom.emailDetailClient.textContent = `${t.ClientName} (${t.TicketStatus})`;
            dom.emailDetailDate.textContent = formatDate(t.ReportDate || t.AddedOnDate);
            dom.emailDetailDescription.textContent = t.Description;
            dom.emailDetailChatBox.classList.add("hidden");

            dom.openTicketInSupportLink.href = `/support?ticket_id=${encodeURIComponent(t.TicketId)}`;
            dom.replyToEmailBtn.onclick = () => {
                openComposeDrawer({
                    to: t.FromEmail || configuredSupportEmail,
                    cc: t.CCEmails || "",
                    ticket_id: t.TicketId,
                    subject: `Re: [Ticket #${t.TicketId}] ${t.Subject}`,
                    body: `\n\n--- Regarding Ticket #${t.TicketId} ---\n${t.Description}`,
                });
            };
        }
    }

    function openComposeDrawer(prefill) {
        dom.composeResultFeedback.className = "form-feedback hidden";
        const data = prefill || {};
        dom.composeTo.value = data.to !== undefined ? data.to : configuredSupportEmail;
        dom.composeCc.value = data.cc || "";
        dom.composeBcc.value = data.bcc || "";
        dom.composeTicketId.value = data.ticket_id ? String(data.ticket_id) : "";
        dom.composeSubject.value = data.subject || "";
        dom.composeBody.value = data.body || "";
        dom.composeModal.classList.remove("hidden");
        dom.composeSubject.focus();
    }

    function closeComposeDrawer() {
        dom.composeModal.classList.add("hidden");
    }

    async function handleSendEmail(event) {
        event.preventDefault();
        dom.composeResultFeedback.className = "form-feedback hidden";

        const toVal = dom.composeTo.value.trim();
        const subjectVal = dom.composeSubject.value.trim();
        const bodyVal = dom.composeBody.value.trim();

        if (!toVal || !subjectVal || !bodyVal) {
            dom.composeResultFeedback.className = "form-feedback banner-error";
            dom.composeResultFeedback.textContent = "Recipient (To), Subject, and Message body are all required.";
            return;
        }

        const payload = {
            to: toVal,
            cc: dom.composeCc.value.trim() || null,
            bcc: dom.composeBcc.value.trim() || null,
            subject: subjectVal,
            body: bodyVal,
            ticket_id: dom.composeTicketId.value ? Number(dom.composeTicketId.value) : null,
        };

        dom.sendEmailSubmitBtn.disabled = true;
        dom.sendEmailSubmitBtn.textContent = "Processing...";

        try {
            const resp = await fetch("/api/emails/send", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || "Email validation or transport error.");
            }

            if (data.sent) {
                dom.composeResultFeedback.className = "form-feedback banner-success";
                dom.composeResultFeedback.textContent =
                    `${data.status_message} ` +
                    (data.recorded_in_db
                        ? "(Outbound MessageId recorded in dbo.TicketEmailMessages.)"
                        : `(${data.db_persistence_detail || ""})`);
                await loadEmails();
            } else {
                // Explicitly report that SMTP is not configured / email was NOT sent
                dom.composeResultFeedback.className = "form-feedback banner-warning";
                dom.composeResultFeedback.textContent =
                    `${data.status_message} ${data.db_persistence_detail || ""}`;
            }
        } catch (err) {
            dom.composeResultFeedback.className = "form-feedback banner-error";
            dom.composeResultFeedback.textContent = err.message;
        } finally {
            dom.sendEmailSubmitBtn.disabled = false;
            dom.sendEmailSubmitBtn.textContent = "Send Email";
        }
    }

    function handleSaveLocalDraft() {
        const draft = {
            id: Date.now(),
            to: dom.composeTo.value.trim(),
            cc: dom.composeCc.value.trim(),
            bcc: dom.composeBcc.value.trim(),
            ticket_id: dom.composeTicketId.value ? Number(dom.composeTicketId.value) : null,
            subject: dom.composeSubject.value.trim(),
            body: dom.composeBody.value.trim(),
            saved_at: new Date().toISOString(),
        };
        const drafts = getLocalDrafts();
        drafts.unshift(draft);
        saveLocalDrafts(drafts.slice(0, 25));

        dom.composeResultFeedback.className = "form-feedback banner-info";
        dom.composeResultFeedback.textContent =
            "Draft saved locally in your browser (Note: JotDeskBuddy_Test does not contain a standalone database table for email drafts).";
        if (currentFolder === "drafts") {
            renderFolderList();
        }
    }

    function bindEvents() {
        dom.openComposeBtn.addEventListener("click", () => openComposeDrawer());
        dom.closeComposeBtn.addEventListener("click", closeComposeDrawer);
        dom.discardComposeBtn.addEventListener("click", () => {
            dom.composeEmailForm.reset();
            closeComposeDrawer();
        });

        dom.fillSupportTeamBtn.addEventListener("click", () => {
            dom.composeTo.value = configuredSupportEmail;
        });

        dom.composeEmailForm.addEventListener("submit", handleSendEmail);
        dom.saveDraftBtn.addEventListener("click", handleSaveLocalDraft);

        dom.folderButtons.forEach((btn) => {
            btn.addEventListener("click", () => {
                dom.folderButtons.forEach((b) => b.classList.remove("active"));
                btn.classList.add("active");
                currentFolder = btn.dataset.folder;
                selectedItemKey = null;
                renderFolderList();
            });
        });

        dom.emailSearchInput.addEventListener("input", () => {
            loadEmails();
        });

        dom.refreshEmailsBtn.addEventListener("click", () => {
            checkDatabaseHealth();
            loadEmails();
        });

        // Support deep-linking from Support Console (/email?ticket_id=...&to=...&subject=...)
        const params = new URLSearchParams(window.location.search);
        if (params.has("ticket_id") || params.has("to") || params.has("subject")) {
            openComposeDrawer({
                ticket_id: params.get("ticket_id") || "",
                to: params.get("to") || configuredSupportEmail,
                subject: params.get("subject") || "",
                body: "",
            });
        }
    }

    document.addEventListener("DOMContentLoaded", async () => {
        bindEvents();
        await checkDatabaseHealth();
        await loadEmails();
    });
})();
