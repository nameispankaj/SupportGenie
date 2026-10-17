const state = { page: 1, pageSize: 10, total: 0, selectedTicketId: null, lastAnalysisText: "" };

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function setText(id, value) { document.getElementById(id).textContent = value; }

async function loadDashboard() {
  setText("dashboard-state", "Loading dashboard...");
  try {
    const data = await api("/api/dashboard");
    const root = document.getElementById("dashboard");
    root.innerHTML = "";
    const metrics = [
      ["Total", data.total_tickets],
      ["Open", data.open_tickets],
      ["In Progress", data.in_progress_tickets],
      ["Closed", data.closed_tickets],
    ];
    metrics.forEach(([label, value]) => {
      const div = document.createElement("div");
      div.className = "metric";
      div.innerHTML = `<strong>${label}</strong><div>${value}</div>`;
      root.appendChild(div);
    });
    setText("dashboard-state", "");
  } catch (err) {
    setText("dashboard-state", err.message);
  }
}

function buildQuery() {
  const form = new FormData(document.getElementById("filters"));
  const params = new URLSearchParams({ page: String(state.page), page_size: String(state.pageSize), sort_by: "report_date", sort_dir: "desc" });
  for (const [k, v] of form.entries()) {
    if (v) params.set(k, v);
  }
  return params.toString();
}

async function loadTickets() {
  setText("tickets-state", "Loading tickets...");
  try {
    const data = await api(`/api/tickets?${buildQuery()}`);
    state.total = data.total_count;
    const body = document.getElementById("tickets-body");
    body.innerHTML = "";
    if (data.items.length === 0) {
      setText("tickets-state", "No tickets found.");
    } else {
      setText("tickets-state", "");
    }
    data.items.forEach((ticket) => {
      const row = document.createElement("tr");
      row.className = "selectable";
      row.innerHTML = `<td>${ticket.ticket_id}</td><td>${ticket.subject}</td><td>${ticket.client || ""}</td><td>${ticket.status || ""}</td><td>${ticket.urgency || ""}</td><td>${ticket.report_date || ""}</td>`;
      row.onclick = () => selectTicket(ticket.ticket_id);
      body.appendChild(row);
    });
    document.getElementById("page-label").textContent = `Page ${state.page}`;
    document.getElementById("prev-page").disabled = state.page <= 1;
    document.getElementById("next-page").disabled = state.page * state.pageSize >= state.total;
  } catch (err) {
    setText("tickets-state", err.message);
  }
}

async function selectTicket(ticketId) {
  state.selectedTicketId = ticketId;
  document.getElementById("analyze-btn").disabled = false;
  document.getElementById("save-note-btn").disabled = false;
  setText("detail-empty", "Loading ticket details...");
  try {
    const detail = await api(`/api/tickets/${ticketId}`);
    const history = await api(`/api/tickets/${ticketId}/history`);
    const detailBox = document.getElementById("ticket-detail");
    detailBox.innerHTML = `<p><strong>${detail.ticket_id}</strong> - ${detail.subject}</p><p>${detail.description}</p><p>Client: ${detail.client || "-"} | Project: ${detail.project || "-"} | Module: ${detail.module || "-"}</p><p>Status: ${detail.status || "-"} | Urgency: ${detail.urgency || "-"} | Assigned: ${detail.assigned_support_associate || "-"}</p>`;

    const list = document.getElementById("ticket-history");
    list.innerHTML = "";
    if (history.history.length === 0) {
      list.innerHTML = "<li>No history available.</li>";
    } else {
      history.history.forEach((item) => {
        const li = document.createElement("li");
        li.textContent = `[${item.source}] ${item.message}`;
        list.appendChild(li);
      });
    }
    setText("detail-empty", "");
  } catch (err) {
    setText("detail-empty", err.message);
  }
}

async function analyzeSelectedTicket() {
  if (!state.selectedTicketId) return;
  setText("analysis-state", "Analyzing ticket...");
  try {
    const result = await api(`/api/tickets/${state.selectedTicketId}/analyze`, { method: "POST" });
    const output = [
      `Category: ${result.ticket_category} (${result.category_confidence})`,
      `Handling Level: ${result.handling_level}`,
      `Explanation: ${result.classification_explanation}`,
      `Suspected Root Cause: ${result.suspected_root_cause}`,
      `Possible Resolution: ${result.possible_resolution}`,
      `Suggested Next Action: ${result.suggested_next_action}`,
      `Evidence:\n- ${result.evidence.join("\n- ") || "None"}`,
      `Unverified Hypotheses:\n- ${result.unverified_hypotheses.join("\n- ") || "None"}`,
      `Missing Information:\n- ${result.missing_information.join("\n- ") || "None"}`,
      `Clarifying Questions:\n- ${result.clarifying_questions.join("\n- ") || "None"}`,
      `Troubleshooting Steps:\n- ${result.troubleshooting_steps.join("\n- ") || "None"}`,
    ].join("\n\n");
    state.lastAnalysisText = output;
    document.getElementById("analysis-result").innerHTML = `<pre>${output}</pre>`;
    document.getElementById("copy-analysis-btn").disabled = false;
    setText("analysis-state", "Analysis completed.");
  } catch (err) {
    setText("analysis-state", err.message);
  }
}

async function saveNote() {
  if (!state.selectedTicketId) return;
  const note = document.getElementById("note-text").value.trim();
  if (!note) return;
  setText("analysis-state", "Saving note...");
  try {
    await api(`/api/tickets/${state.selectedTicketId}/notes`, {
      method: "POST",
      body: JSON.stringify({ note }),
    });
    document.getElementById("note-text").value = "";
    await selectTicket(state.selectedTicketId);
    setText("analysis-state", "Note recorded.");
  } catch (err) {
    setText("analysis-state", err.message);
  }
}

document.getElementById("filters").addEventListener("submit", async (event) => {
  event.preventDefault();
  state.page = 1;
  await loadTickets();
});
document.getElementById("prev-page").onclick = async () => { state.page -= 1; await loadTickets(); };
document.getElementById("next-page").onclick = async () => { state.page += 1; await loadTickets(); };
document.getElementById("analyze-btn").onclick = analyzeSelectedTicket;
document.getElementById("save-note-btn").onclick = saveNote;
document.getElementById("copy-analysis-btn").onclick = async () => {
  await navigator.clipboard.writeText(state.lastAnalysisText);
  setText("analysis-state", "Analysis copied.");
};

loadDashboard();
loadTickets();
