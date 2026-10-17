/**
 * SupportGenie — Support Ticket Management Frontend Script (support.js)
 * Connects to the FastAPI backend (/api/dashboard, /api/tickets, /api/tickets/{id},
 * /api/tickets/{id}/analyze, /api/tickets/{id}/comments, /api/tickets/{id}/status).
 * Never fabricates dashboard counts or fake database updates.
 */

(function () {
    "use strict";

    let currentTickets = [];
    let selectedTicketId = null;
    let selectedTicketData = null;
    let lastNlpResult = null;
    let associatesList = [];

    const dom = {
        dbBadge: document.getElementById("dbConnectionBadge"),
        dbText: document.getElementById("dbConnectionText"),
        globalAssociateSelect: document.getElementById("globalAssociateSelect"),

        statTotal: document.getElementById("statTotal"),
        statOpen: document.getElementById("statOpen"),
        statInProgress: document.getElementById("statInProgress"),
        statResolved: document.getElementById("statResolved"),
        statHighPriority: document.getElementById("statHighPriority"),
        statAssigned: document.getElementById("statAssigned"),
        statAssignedName: document.getElementById("statAssignedName"),
        statAssignedCard: document.getElementById("statAssignedCard"),

        searchInput: document.getElementById("ticketSearchInput"),
        filterStatus: document.getElementById("filterStatus"),
        filterCategory: document.getElementById("filterCategory"),
        filterPriority: document.getElementById("filterPriority"),
        filterAssociate: document.getElementById("filterAssociate"),
        clearFiltersBtn: document.getElementById("clearFiltersBtn"),
        refreshTicketsBtn: document.getElementById("refreshTicketsBtn"),

        ticketCountBadge: document.getElementById("ticketCountBadge"),
        ticketListStateBanner: document.getElementById("ticketListStateBanner"),
        ticketTableBody: document.getElementById("ticketTableBody"),

        noTicketSelectedView: document.getElementById("noTicketSelectedView"),
        ticketDetailContent: document.getElementById("ticketDetailContent"),
        detailTicketId: document.getElementById("detailTicketId"),
        detailStatusBadge: document.getElementById("detailStatusBadge"),
        detailPriorityBadge: document.getElementById("detailPriorityBadge"),
        detailCategoryBadge: document.getElementById("detailCategoryBadge"),
        detailSubject: document.getElementById("detailSubject"),
        detailClient: document.getElementById("detailClient"),
        detailModule: document.getElementById("detailModule"),
        detailAssignee: document.getElementById("detailAssignee"),
        detailReporter: document.getElementById("detailReporter"),
        detailMethod: document.getElementById("detailMethod"),
        detailCreated: document.getElementById("detailCreated"),
        detailUpdated: document.getElementById("detailUpdated"),
        detailSLA: document.getElementById("detailSLA"),
        detailDescription: document.getElementById("detailDescription"),
        detailResolutionBox: document.getElementById("detailResolutionBox"),
        detailRemarkText: document.getElementById("detailRemarkText"),
        detailClosedMeta: document.getElementById("detailClosedMeta"),

        analyzeTicketBtn: document.getElementById("analyzeTicketBtn"),
        composeEmailForTicketBtn: document.getElementById("composeEmailForTicketBtn"),

        nlpAnalysisPanel: document.getElementById("nlpAnalysisPanel"),
        nlpPredictedCategory: document.getElementById("nlpPredictedCategory"),
        nlpConfidenceBadge: document.getElementById("nlpConfidenceBadge"),
        nlpConfidenceExplanation: document.getElementById("nlpConfidenceExplanation"),
        nlpRootCause: document.getElementById("nlpRootCause"),
        nlpResolutionSteps: document.getElementById("nlpResolutionSteps"),
        nlpEvidenceList: document.getElementById("nlpEvidenceList"),
        nlpMissingList: document.getElementById("nlpMissingList"),
        nlpHistoricalSummary: document.getElementById("nlpHistoricalSummary"),
        nlpHistoricalList: document.getElementById("nlpHistoricalList"),
        copyNlpToNoteBtn: document.getElementById("copyNlpToNoteBtn"),
        applyPredictedCategoryBtn: document.getElementById("applyPredictedCategoryBtn"),

        updateTicketForm: document.getElementById("updateTicketForm"),
        updateStatusSelect: document.getElementById("updateStatusSelect"),
        updatePicSelect: document.getElementById("updatePicSelect"),
        updateCategorySelect: document.getElementById("updateCategorySelect"),
        updatePrioritySelect: document.getElementById("updatePrioritySelect"),
        updateRemarkInput: document.getElementById("updateRemarkInput"),
        updateHoursInput: document.getElementById("updateHoursInput"),
        saveTicketUpdateBtn: document.getElementById("saveTicketUpdateBtn"),
        updateTicketFeedback: document.getElementById("updateTicketFeedback"),

        addCommentForm: document.getElementById("addCommentForm"),
        commentTypeSelect: document.getElementById("commentTypeSelect"),
        commentTextInput: document.getElementById("commentTextInput"),
        submitCommentBtn: document.getElementById("submitCommentBtn"),
        addCommentFeedback: document.getElementById("addCommentFeedback"),

        countFollowups: document.getElementById("countFollowups"),
        countChats: document.getElementById("countChats"),
        countEmails: document.getElementById("countEmails"),
        countAudits: document.getElementById("countAudits"),
        tabPanelFollowups: document.getElementById("tabPanelFollowups"),
        tabPanelChats: document.getElementById("tabPanelChats"),
        tabPanelEmails: document.getElementById("tabPanelEmails"),
        tabPanelAudits: document.getElementById("tabPanelAudits"),
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

    function getStatusBadgeClass(status) {
        const s = (status || "").toLowerCase();
        if (s === "open") return "badge badge-open";
        if (s === "in progress") return "badge badge-progress";
        if (s === "closed" || s === "resolved") return "badge badge-closed";
        return "badge badge-neutral";
    }

    function getPriorityBadgeClass(priority) {
        const p = (priority || "").toLowerCase();
        if (p === "high" || p === "urgent" || p === "critical") return "badge badge-high";
        if (p === "medium") return "badge badge-medium";
        return "badge badge-low";
    }

    function getActiveAssociate() {
        const sel = dom.globalAssociateSelect;
        if (!sel || !sel.selectedOptions.length) {
            return {
                id: Number(document.body.dataset.defaultAssociateId || 1),
                name: document.body.dataset.defaultAssociateName || "Demo L1 Associate",
            };
        }
        const opt = sel.selectedOptions[0];
        return {
            id: Number(opt.value || 1),
            name: opt.dataset.name || opt.textContent.trim(),
        };
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

    function populateFilterDropdowns(filters) {
        if (!filters) return;

        if (Array.isArray(filters.associates) && filters.associates.length > 0) {
            associatesList = filters.associates;
            const currentId = getActiveAssociate().id;
            dom.globalAssociateSelect.innerHTML = filters.associates
                .map(
                    (a) =>
                        `<option value="${escapeHtml(a.Id)}" data-name="${escapeHtml(a.Name)}" ${
                            Number(a.Id) === currentId ? "selected" : ""
                        }>${escapeHtml(a.Name)}</option>`
                )
                .join("");

            const currentFilterPic = dom.filterAssociate.value;
            dom.filterAssociate.innerHTML =
                `<option value="">All Associates (PIC)</option>` +
                filters.associates
                    .map((a) => `<option value="${escapeHtml(a.Name)}">${escapeHtml(a.Name)}</option>`)
                    .join("");
            dom.filterAssociate.value = currentFilterPic;

            dom.updatePicSelect.innerHTML =
                `<option value="">-- Keep Current --</option>` +
                filters.associates
                    .map((a) => `<option value="${escapeHtml(a.Id)}">${escapeHtml(a.Name)} (${escapeHtml(a.Email)})</option>`)
                    .join("");
        }

        if (Array.isArray(filters.statuses)) {
            const cur = dom.filterStatus.value;
            dom.filterStatus.innerHTML =
                `<option value="">All Statuses</option>` +
                filters.statuses.map((s) => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
            dom.filterStatus.value = cur;
        }

        if (Array.isArray(filters.categories)) {
            const cur = dom.filterCategory.value;
            dom.filterCategory.innerHTML =
                `<option value="">All Categories (TicketTypeName)</option>` +
                filters.categories.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
            dom.filterCategory.value = cur;

            dom.updateCategorySelect.innerHTML = filters.categories
                .map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`)
                .join("");
        }

        if (Array.isArray(filters.priorities)) {
            const cur = dom.filterPriority.value;
            dom.filterPriority.innerHTML =
                `<option value="">All Priorities</option>` +
                filters.priorities.map((p) => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join("");
            dom.filterPriority.value = cur;
        }
    }

    async function loadDashboard() {
        const assoc = getActiveAssociate();
        dom.statAssignedName.textContent = assoc.name;
        try {
            const params = new URLSearchParams({
                associate_id: String(assoc.id),
                associate_name: assoc.name,
            });
            const resp = await fetch(`/api/dashboard?${params.toString()}`);
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || "Failed to load dashboard counts.");
            }
            const c = data.counts || {};
            dom.statTotal.textContent = c.total_tickets ?? 0;
            dom.statOpen.textContent = c.open_tickets ?? 0;
            dom.statInProgress.textContent = c.in_progress_tickets ?? 0;
            dom.statResolved.textContent = c.resolved_tickets ?? 0;
            dom.statHighPriority.textContent = c.high_priority_tickets ?? 0;
            dom.statAssigned.textContent = c.assigned_to_associate ?? 0;
            populateFilterDropdowns(data.filters);
        } catch (err) {
            dom.statTotal.textContent = "Err";
            dom.statOpen.textContent = "--";
            dom.statInProgress.textContent = "--";
            dom.statResolved.textContent = "--";
            dom.statHighPriority.textContent = "--";
            dom.statAssigned.textContent = "--";
        }
    }

    async function loadTickets() {
        dom.ticketListStateBanner.className = "state-banner hidden";
        dom.ticketTableBody.innerHTML = `<tr><td colspan="7" class="empty-cell">Loading tickets from SQL Server...</td></tr>`;

        const params = new URLSearchParams();
        if (dom.searchInput.value.trim()) params.set("search", dom.searchInput.value.trim());
        if (dom.filterStatus.value) params.set("status", dom.filterStatus.value);
        if (dom.filterCategory.value) params.set("category", dom.filterCategory.value);
        if (dom.filterPriority.value) params.set("priority", dom.filterPriority.value);
        if (dom.filterAssociate.value) params.set("assigned_pic", dom.filterAssociate.value);

        try {
            const resp = await fetch(`/api/tickets?${params.toString()}`);
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || "Unable to fetch tickets from SQL Server.");
            }
            currentTickets = data.tickets || [];
            dom.ticketCountBadge.textContent = `${currentTickets.length} ticket${currentTickets.length === 1 ? "" : "s"}`;
            renderTicketRows();
        } catch (err) {
            currentTickets = [];
            dom.ticketCountBadge.textContent = "Error";
            dom.ticketListStateBanner.className = "state-banner banner-error";
            dom.ticketListStateBanner.textContent = err.message;
            dom.ticketTableBody.innerHTML = `<tr><td colspan="7" class="empty-cell">Could not load tickets. Check SQL Server connection in .env.</td></tr>`;
        }
    }

    function renderTicketRows() {
        if (!currentTickets.length) {
            dom.ticketTableBody.innerHTML = `<tr><td colspan="7" class="empty-cell">No tickets match the current search or filters.</td></tr>`;
            return;
        }
        dom.ticketTableBody.innerHTML = currentTickets
            .map((t) => {
                const isSelected = Number(t.TicketId) === Number(selectedTicketId);
                return `
                <tr data-ticket-id="${escapeHtml(t.TicketId)}" class="${isSelected ? "selected-row" : ""}">
                    <td><span class="ticket-id-chip">#${escapeHtml(t.TicketId)}</span></td>
                    <td>
                        <span class="ticket-subject-cell">${escapeHtml(t.Subject)}</span>
                        <span class="ticket-client-sub">${escapeHtml(t.ClientName)} &bull; ${escapeHtml(t.ModuleName || "Unassigned Module")}</span>
                    </td>
                    <td><span class="badge badge-category">${escapeHtml(t.Category)}</span></td>
                    <td><span class="${getPriorityBadgeClass(t.Priority)}">${escapeHtml(t.Priority)}</span></td>
                    <td><span class="${getStatusBadgeClass(t.Status)}">${escapeHtml(t.Status)}</span></td>
                    <td>${escapeHtml(t.AssignedAssociate || "Unassigned")}</td>
                    <td>${escapeHtml(formatDate(t.CreatedDate).substring(0, 10))}</td>
                </tr>
            `;
            })
            .join("");

        Array.from(dom.ticketTableBody.querySelectorAll("tr[data-ticket-id]")).forEach((row) => {
            row.addEventListener("click", () => {
                const id = Number(row.dataset.ticketId);
                selectTicket(id);
            });
        });
    }

    async function selectTicket(ticketId) {
        selectedTicketId = ticketId;
        lastNlpResult = null;
        dom.nlpAnalysisPanel.classList.add("hidden");
        dom.updateTicketFeedback.classList.add("hidden");
        dom.addCommentFeedback.classList.add("hidden");
        renderTicketRows();

        try {
            const resp = await fetch(`/api/tickets/${ticketId}`);
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || `Failed to load ticket #${ticketId}`);
            }
            selectedTicketData = data.ticket;
            renderTicketDetail(data.ticket, data.history);
        } catch (err) {
            dom.noTicketSelectedView.classList.remove("hidden");
            dom.noTicketSelectedView.innerHTML = `<h3>Error Loading Ticket #${escapeHtml(ticketId)}</h3><p>${escapeHtml(err.message)}</p>`;
            dom.ticketDetailContent.classList.add("hidden");
        }
    }

    function renderTicketDetail(t, history) {
        dom.noTicketSelectedView.classList.add("hidden");
        dom.ticketDetailContent.classList.remove("hidden");

        dom.detailTicketId.textContent = `#${t.TicketId}`;
        dom.detailStatusBadge.className = getStatusBadgeClass(t.Status);
        dom.detailStatusBadge.textContent = t.Status;
        dom.detailPriorityBadge.className = getPriorityBadgeClass(t.Priority);
        dom.detailPriorityBadge.textContent = `${t.Priority} Priority`;
        dom.detailCategoryBadge.textContent = t.Category;

        dom.detailSubject.textContent = t.Subject;
        dom.detailClient.textContent = `${t.ClientName} (${t.ClientShortCode || "N/A"})`;
        dom.detailModule.textContent = `${t.ProjectName || "N/A"} / ${t.ModuleName || "Unspecified"}`;
        dom.detailAssignee.textContent = t.AssignedAssociate || "Unassigned";
        dom.detailReporter.textContent = `${t.AddedByName || "Unknown"} (${t.FromEmail || "No email"})`;
        dom.detailMethod.textContent = t.ReportedMethodName || "N/A";
        dom.detailCreated.textContent = formatDate(t.CreatedDate);
        dom.detailUpdated.textContent = formatDate(t.UpdatedDate);
        dom.detailSLA.textContent = t.SLAHours ? `${t.SLAHours} hrs` : "Standard";
        dom.detailDescription.textContent = t.Description;

        if (t.Remark || t.ClosedOn) {
            dom.detailResolutionBox.classList.remove("hidden");
            dom.detailRemarkText.textContent = t.Remark || "No resolution text recorded.";
            dom.detailClosedMeta.textContent = t.ClosedOn
                ? `Closed by ${t.ClosedBy || "Associate"} on ${formatDate(t.ClosedOn)} (${t.HoursSpentToClose || 0} hrs spent, Within SLA: ${t.IsClosedWithinSLA ? "Yes" : "No"})`
                : "";
        } else {
            dom.detailResolutionBox.classList.add("hidden");
        }

        // Pre-populate update form with current ticket values
        dom.updateStatusSelect.value = t.Status || "Open";
        dom.updatePicSelect.value = t.PICId ? String(t.PICId) : "";
        dom.updateCategorySelect.value = t.Category || "Product Bug";
        dom.updatePrioritySelect.value = t.Priority || "Medium";
        dom.updateRemarkInput.value = t.Remark || "";
        dom.updateHoursInput.value = t.HoursSpentToClose ? String(t.HoursSpentToClose) : "";

        // Update Email link with query params
        const emailParams = new URLSearchParams({
            ticket_id: String(t.TicketId),
            to: t.FromEmail || t.ClientEmail || "",
            subject: `Re: [Ticket #${t.TicketId}] ${t.Subject}`,
        });
        dom.composeEmailForTicketBtn.href = `/email?${emailParams.toString()}`;

        renderTicketHistory(history);
    }

    function renderTicketHistory(history) {
        const followups = (history && history.followups) || [];
        const chats = (history && history.chats) || [];
        const emails = (history && history.email_messages) || [];
        const audits = (history && history.update_logs) || [];

        dom.countFollowups.textContent = followups.length;
        dom.countChats.textContent = chats.length;
        dom.countEmails.textContent = emails.length;
        dom.countAudits.textContent = audits.length;

        dom.tabPanelFollowups.innerHTML = followups.length
            ? followups
                  .map((f) => {
                      const atts = (f.Attachments || [])
                          .map(
                              (a) =>
                                  `<div class="attachment-chip">Attachment: ${escapeHtml(a.AttachmentName)} (${escapeHtml(
                                      a.AttachmentSize || 0
                                  )} bytes)</div>`
                          )
                          .join("");
                      return `
                    <div class="timeline-item">
                        <div class="timeline-item-header">
                            <strong>#${escapeHtml(f.FollowupRunningNumber || f.Id)} &bull; ${escapeHtml(f.AddedByName)}</strong>
                            <span>${escapeHtml(formatDate(f.AddedOnDate))}</span>
                        </div>
                        <div>${escapeHtml(f.Remarks)}</div>
                        ${atts}
                    </div>
                `;
                  })
                  .join("")
            : `<p class="muted-note">No internal follow-up notes recorded in dbo.TicketFollowups for this ticket.</p>`;

        dom.tabPanelChats.innerHTML = chats.length
            ? chats
                  .map((c) => {
                      const atts = (c.Attachments || [])
                          .map(
                              (a) =>
                                  `<div class="attachment-chip">Attachment: ${escapeHtml(a.AttachmentName)} (${escapeHtml(
                                      a.AttachmentSize || 0
                                  )} bytes)</div>`
                          )
                          .join("");
                      return `
                    <div class="timeline-item">
                        <div class="timeline-item-header">
                            <strong>#${escapeHtml(c.ChatRunningNumber || c.Id)} &bull; ${escapeHtml(c.AddedByName)}</strong>
                            <span>${escapeHtml(formatDate(c.AddedOnDate))}</span>
                        </div>
                        <div>${escapeHtml(c.Chat)}</div>
                        ${atts}
                    </div>
                `;
                  })
                  .join("")
            : `<p class="muted-note">No conversation entries recorded in dbo.TicketChat for this ticket.</p>`;

        dom.tabPanelEmails.innerHTML = emails.length
            ? emails
                  .map(
                      (em) => `
                <div class="timeline-item">
                    <div class="timeline-item-header">
                        <strong>${em.IsOutgoing ? "Outbound (Sent)" : "Inbound (Inbox)"} &bull; ${escapeHtml(em.AddedByName)}</strong>
                        <span>${escapeHtml(formatDate(em.AddedOnDate))}</span>
                    </div>
                    <div>MessageId: <code>${escapeHtml(em.MessageId)}</code></div>
                </div>
            `
                  )
                  .join("")
            : `<p class="muted-note">No email message metadata linked in dbo.TicketEmailMessages for this ticket.</p>`;

        dom.tabPanelAudits.innerHTML = audits.length
            ? audits
                  .map(
                      (u) => `
                <div class="timeline-item">
                    <div class="timeline-item-header">
                        <strong>Updated by ${escapeHtml(u.UpdatedByName)}</strong>
                        <span>${escapeHtml(formatDate(u.UpdatedOnDate))}</span>
                    </div>
                    <div><code>${escapeHtml(u.Data)}</code></div>
                </div>
            `
                  )
                  .join("")
            : `<p class="muted-note">No update logs in dbo.UpdateLogs for this ticket.</p>`;
    }

    async function runNlpAnalysis() {
        if (!selectedTicketId) return;
        dom.analyzeTicketBtn.disabled = true;
        dom.analyzeTicketBtn.textContent = "Analyzing...";

        try {
            const resp = await fetch(`/api/tickets/${selectedTicketId}/analyze`, {
                method: "POST",
            });
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || "NLP analysis failed.");
            }
            lastNlpResult = data;
            renderNlpAnalysis(data);
        } catch (err) {
            dom.updateTicketFeedback.className = "form-feedback banner-error";
            dom.updateTicketFeedback.textContent = err.message;
        } finally {
            dom.analyzeTicketBtn.disabled = false;
            dom.analyzeTicketBtn.textContent = "Analyze Ticket (NLP)";
        }
    }

    function renderNlpAnalysis(nlp) {
        dom.nlpAnalysisPanel.classList.remove("hidden");
        dom.nlpPredictedCategory.textContent = `Predicted: ${nlp.predicted_category}`;
        dom.nlpConfidenceBadge.className =
            nlp.confidence_label === "High"
                ? "badge badge-closed"
                : nlp.confidence_label === "Medium"
                ? "badge badge-progress"
                : "badge badge-neutral";
        dom.nlpConfidenceBadge.textContent = `Rule Confidence: ${Math.round((nlp.confidence_score || 0) * 100)}% (${nlp.confidence_label})`;
        dom.nlpConfidenceExplanation.textContent = nlp.confidence_explanation || "";
        dom.nlpRootCause.textContent = nlp.root_cause || "";

        dom.nlpResolutionSteps.innerHTML = (nlp.resolution_steps || [])
            .map((step) => `<li>${escapeHtml(step)}</li>`)
            .join("");

        dom.nlpEvidenceList.innerHTML = (nlp.supporting_evidence || [])
            .map((ev) => `<li>${escapeHtml(ev)}</li>`)
            .join("");

        dom.nlpMissingList.innerHTML = (nlp.missing_information || []).length
            ? nlp.missing_information.map((m) => `<li>${escapeHtml(m)}</li>`).join("")
            : `<li>No additional missing fields flagged by rules.</li>`;

        dom.nlpHistoricalSummary.textContent = nlp.historical_summary || "";
        const hist = nlp.historical_tickets || [];
        dom.nlpHistoricalList.innerHTML = hist.length
            ? hist
                  .map(
                      (h) => `
                <div class="hist-card">
                    <div><strong>Ticket #${escapeHtml(h.ticket_id)}:</strong> ${escapeHtml(h.subject)}</div>
                    <div class="muted-note">Category: ${escapeHtml(h.category)} &bull; Status: ${escapeHtml(h.status)}</div>
                    ${
                        h.resolution_remark
                            ? `<div style="margin-top:4px;"><strong>Recorded Resolution:</strong> ${escapeHtml(h.resolution_remark)}</div>`
                            : h.latest_followup
                            ? `<div style="margin-top:4px;"><strong>Latest Follow-up:</strong> ${escapeHtml(h.latest_followup)}</div>`
                            : ""
                    }
                    <div class="muted-note" style="margin-top:4px;">Match: ${(h.match_reasons || []).map(escapeHtml).join(" | ")}</div>
                </div>
            `
                  )
                  .join("")
            : "";
    }

    async function handleUpdateTicket(event) {
        event.preventDefault();
        if (!selectedTicketId) return;

        const assoc = getActiveAssociate();
        const payload = {
            status: dom.updateStatusSelect.value,
            pic_id: dom.updatePicSelect.value ? Number(dom.updatePicSelect.value) : null,
            category: dom.updateCategorySelect.value,
            priority: dom.updatePrioritySelect.value,
            remark: dom.updateRemarkInput.value.trim(),
            hours_spent: dom.updateHoursInput.value ? Number(dom.updateHoursInput.value) : null,
            updated_by: assoc.id,
            updated_by_name: assoc.name,
        };

        dom.saveTicketUpdateBtn.disabled = true;
        dom.updateTicketFeedback.className = "form-feedback hidden";

        try {
            const resp = await fetch(`/api/tickets/${selectedTicketId}/status`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || "Failed to update ticket in SQL Server.");
            }
            dom.updateTicketFeedback.className = "form-feedback banner-success";
            dom.updateTicketFeedback.textContent = data.message || "Ticket updated in SQL Server.";
            await Promise.all([loadDashboard(), loadTickets(), selectTicket(selectedTicketId)]);
        } catch (err) {
            dom.updateTicketFeedback.className = "form-feedback banner-error";
            dom.updateTicketFeedback.textContent = err.message;
        } finally {
            dom.saveTicketUpdateBtn.disabled = false;
        }
    }

    async function handleAddComment(event) {
        event.preventDefault();
        if (!selectedTicketId) return;

        const text = dom.commentTextInput.value.trim();
        if (!text) return;

        const assoc = getActiveAssociate();
        const payload = {
            text: text,
            note_type: dom.commentTypeSelect.value,
            added_by: assoc.id,
            added_by_name: assoc.name,
        };

        dom.submitCommentBtn.disabled = true;
        dom.addCommentFeedback.className = "form-feedback hidden";

        try {
            const resp = await fetch(`/api/tickets/${selectedTicketId}/comments`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || "Failed to save note to SQL Server.");
            }
            dom.commentTextInput.value = "";
            dom.addCommentFeedback.className = "form-feedback banner-success";
            dom.addCommentFeedback.textContent = data.message || "Saved to SQL Server.";
            await Promise.all([loadTickets(), selectTicket(selectedTicketId)]);
        } catch (err) {
            dom.addCommentFeedback.className = "form-feedback banner-error";
            dom.addCommentFeedback.textContent = err.message;
        } finally {
            dom.submitCommentBtn.disabled = false;
        }
    }

    function bindEvents() {
        dom.searchInput.addEventListener("input", () => {
            loadTickets();
        });
        [dom.filterStatus, dom.filterCategory, dom.filterPriority, dom.filterAssociate].forEach((sel) => {
            sel.addEventListener("change", () => loadTickets());
        });

        dom.clearFiltersBtn.addEventListener("click", () => {
            dom.searchInput.value = "";
            dom.filterStatus.value = "";
            dom.filterCategory.value = "";
            dom.filterPriority.value = "";
            dom.filterAssociate.value = "";
            loadTickets();
        });

        dom.refreshTicketsBtn.addEventListener("click", () => {
            checkDatabaseHealth();
            loadDashboard();
            loadTickets();
            if (selectedTicketId) selectTicket(selectedTicketId);
        });

        if (dom.globalAssociateSelect) {
            dom.globalAssociateSelect.addEventListener("change", () => {
                loadDashboard();
            });
        }

        // Dashboard card quick filters
        document.querySelectorAll(".stat-card[data-filter-status]").forEach((card) => {
            card.addEventListener("click", () => {
                dom.filterStatus.value = card.dataset.filterStatus || "";
                dom.filterPriority.value = "";
                dom.filterAssociate.value = "";
                loadTickets();
            });
        });

        document.querySelectorAll(".stat-card[data-filter-priority]").forEach((card) => {
            card.addEventListener("click", () => {
                dom.filterPriority.value = card.dataset.filterPriority || "";
                dom.filterStatus.value = "";
                loadTickets();
            });
        });

        if (dom.statAssignedCard) {
            dom.statAssignedCard.addEventListener("click", () => {
                const assoc = getActiveAssociate();
                dom.filterAssociate.value = assoc.name;
                loadTickets();
            });
        }

        dom.analyzeTicketBtn.addEventListener("click", runNlpAnalysis);
        dom.updateTicketForm.addEventListener("submit", handleUpdateTicket);
        dom.addCommentForm.addEventListener("submit", handleAddComment);

        dom.copyNlpToNoteBtn.addEventListener("click", () => {
            if (!lastNlpResult) return;
            dom.commentTypeSelect.value = "followup";
            dom.commentTextInput.value =
                `[NLP Analysis Draft - ${lastNlpResult.predicted_category}] ` +
                `${lastNlpResult.root_cause} Next step: ${lastNlpResult.recommended_next_action}`;
            dom.commentTextInput.focus();
        });

        dom.applyPredictedCategoryBtn.addEventListener("click", () => {
            if (!lastNlpResult) return;
            dom.updateCategorySelect.value = lastNlpResult.predicted_category;
            dom.updateCategorySelect.focus();
        });

        // History tabs
        document.querySelectorAll(".history-tab").forEach((tabBtn) => {
            tabBtn.addEventListener("click", () => {
                document.querySelectorAll(".history-tab").forEach((b) => b.classList.remove("active"));
                tabBtn.classList.add("active");
                const target = tabBtn.dataset.tab;
                dom.tabPanelFollowups.classList.toggle("hidden", target !== "followups");
                dom.tabPanelChats.classList.toggle("hidden", target !== "chats");
                dom.tabPanelEmails.classList.toggle("hidden", target !== "emails");
                dom.tabPanelAudits.classList.toggle("hidden", target !== "audits");
            });
        });

        // Check URL parameters for ticket_id deep link
        const urlParams = new URLSearchParams(window.location.search);
        const deepTicketId = urlParams.get("ticket_id");
        if (deepTicketId && !Number.isNaN(Number(deepTicketId))) {
            selectedTicketId = Number(deepTicketId);
        }
    }

    document.addEventListener("DOMContentLoaded", async () => {
        bindEvents();
        await checkDatabaseHealth();
        await loadDashboard();
        await loadTickets();
        if (selectedTicketId) {
            await selectTicket(selectedTicketId);
        } else if (currentTickets.length > 0) {
            await selectTicket(currentTickets[0].TicketId);
        }
    });
})();
