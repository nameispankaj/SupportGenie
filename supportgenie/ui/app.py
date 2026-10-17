import streamlit as st

from supportgenie.config import settings
from supportgenie.data.synthetic_tickets import SYNTHETIC_TICKETS
from supportgenie.db.factory import get_ticket_repository
from supportgenie.db.repository import AccessDeniedError
from supportgenie.services.analysis_service import TicketAnalysisService
from supportgenie.ui.helpers import (
    backend_setup_message,
    compose_issue_summary,
    recommended_response_for,
    sentiment_for,
    urgency_for,
)

st.set_page_config(page_title="SupportGenie", page_icon="🛟", layout="wide")

APP_STYLE = """
<style>
    .main-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.1rem; }
    .subtitle { color: #8b9097; margin-bottom: 1.2rem; }
    .result-box { border: 1px solid #2d2f36; border-radius: 12px; padding: 1rem; margin-bottom: 0.8rem; }
</style>
"""
st.markdown(APP_STYLE, unsafe_allow_html=True)


def _analyze_ticket(tenant_id: str, user_id: str, ticket_id: str | None, issue_summary: str):
    ticket = None
    if ticket_id:
        repository = get_ticket_repository()
        ticket = repository.get_ticket_by_id(ticket_id=ticket_id, tenant_id=tenant_id, user_id=user_id)
        if not ticket:
            raise ValueError(f"Ticket '{ticket_id}' was not found for tenant '{tenant_id}'.")
        issue_summary = ticket.issue_description

    if not issue_summary:
        raise ValueError("Issue subject or description is required when ticket ID is not provided.")

    service = TicketAnalysisService()
    result = service.analyze(tenant_id=tenant_id, issue_summary=issue_summary, ticket=ticket)
    return result, ticket


setup_message = backend_setup_message(
    demo_mode=settings.demo_mode,
    azure_ai_foundry_endpoint=settings.azure_ai_foundry_endpoint,
    azure_ai_foundry_api_key=settings.azure_ai_foundry_api_key,
    azure_ai_search_endpoint=settings.azure_ai_search_endpoint,
    azure_ai_search_api_key=settings.azure_ai_search_api_key,
    azure_ai_search_index_name=settings.azure_ai_search_index_name,
    sql_server_connection_string=settings.sql_server_connection_string,
)

st.sidebar.title("🛟 SupportGenie")
st.sidebar.caption("Enterprise Support Ticket Intelligence")
page = st.sidebar.radio("Navigation", ["Dashboard", "Analyze Ticket", "Demo Tickets"])
tenant_id = st.sidebar.text_input("Tenant ID", value=settings.ui_default_tenant_id)
user_id = st.sidebar.text_input("User ID", value=settings.ui_default_user_id)

demo_ticket_ids = [ticket["ticket_id"] for ticket in SYNTHETIC_TICKETS]
selected_ticket_id = st.sidebar.selectbox("Quick sample ticket", [""] + demo_ticket_ids)

st.markdown('<div class="main-title">SupportGenie</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">AI-assisted support ticket triage and response guidance</div>', unsafe_allow_html=True)

if settings.demo_mode:
    st.info(setup_message)
else:
    st.warning(setup_message)

if page == "Dashboard":
    categories = {ticket["category"] for ticket in SYNTHETIC_TICKETS}
    col1, col2, col3 = st.columns(3)
    col1.metric("Demo Tickets", len(SYNTHETIC_TICKETS))
    col2.metric("Covered Categories", len(categories))
    col3.metric("Mode", "Demo" if settings.demo_mode else "Live")
    st.markdown("### Recent Demo Tickets")
    st.dataframe(
        [
            {
                "ticket_id": ticket["ticket_id"],
                "tenant_id": ticket["tenant_id"],
                "module": ticket["module"],
                "category": ticket["category"],
            }
            for ticket in SYNTHETIC_TICKETS
        ],
        use_container_width=True,
        hide_index=True,
    )

if page == "Analyze Ticket":
    st.markdown("### Ticket Input")
    input_mode = st.radio("Input Source", ["Existing Ticket ID", "Manual Ticket Text"], horizontal=True)
    ticket_id = selected_ticket_id if selected_ticket_id else ""
    subject = ""
    description = ""

    if input_mode == "Existing Ticket ID":
        ticket_id = st.text_input("Ticket ID", value=ticket_id, placeholder="e.g., TKT-1001")
    else:
        subject = st.text_input("Subject", placeholder="e.g., API sync failing with 401")
        description = st.text_area("Description", placeholder="Describe issue details, impact, and timeline")
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Priority", ["P1", "P2", "P3", "P4"], index=1)
        with col2:
            st.selectbox("Category Hint", ["Unknown", "Bug", "Data", "Integration", "Access", "Configuration"])

    if st.button("Analyze Ticket", type="primary"):
        issue_summary = compose_issue_summary(subject, description)
        try:
            with st.spinner("Analyzing ticket..."):
                analysis, ticket = _analyze_ticket(tenant_id, user_id, ticket_id or None, issue_summary)
        except AccessDeniedError as exc:
            st.error(f"Authorization error: {exc}")
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:  # pragma: no cover - defensive UI guard
            st.error(f"Unexpected analysis error: {exc}")
        else:
            st.success("Analysis complete.")
            st.markdown("### Analysis Results")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Intent / Category", analysis.category.value)
            col2.metric("Sentiment", sentiment_for(analysis.category))
            col3.metric("Urgency", urgency_for(analysis.category, analysis.confidence))
            col4.metric("Confidence", analysis.confidence.value.upper())

            st.markdown('<div class="result-box"><b>Summary</b><br/>' + analysis.context.issue_summary + "</div>", unsafe_allow_html=True)
            st.markdown(
                '<div class="result-box"><b>Recommended Response</b><br/>'
                + recommended_response_for(analysis)
                + "</div>",
                unsafe_allow_html=True,
            )

            with st.expander("Likely Root Cause", expanded=True):
                st.write(analysis.likely_root_cause)
            with st.expander("Verified Evidence"):
                if analysis.verified_evidence:
                    for item in analysis.verified_evidence:
                        st.write(f"- {item}")
                elif ticket:
                    st.write("No evidence entries available.")
                else:
                    st.write("Manual input analysis does not include ticket history evidence.")
            with st.expander("Retrieval / Source Context"):
                if analysis.related_knowledge:
                    for item in analysis.related_knowledge:
                        st.write(f"- {item}")
                else:
                    st.write("No related knowledge returned.")
            with st.expander("Missing Information"):
                if analysis.missing_information:
                    for item in analysis.missing_information:
                        st.write(f"- {item}")
                else:
                    st.write("No additional information required.")
            with st.expander("Clarifying Questions"):
                if analysis.clarifying_questions:
                    for item in analysis.clarifying_questions:
                        st.write(f"- {item}")
                else:
                    st.write("No clarifying questions generated.")
    else:
        st.info("Provide ticket details and click **Analyze Ticket**.")

if page == "Demo Tickets":
    st.markdown("### Example Tickets")
    st.caption("Use these sample records when running in demo mode.")
    st.dataframe(
        [
            {
                "ticket_id": ticket["ticket_id"],
                "tenant_id": ticket["tenant_id"],
                "client": ticket["client"],
                "module": ticket["module"],
                "category": ticket["category"],
                "issue_description": ticket["issue_description"],
            }
            for ticket in SYNTHETIC_TICKETS
        ],
        use_container_width=True,
        hide_index=True,
    )
