from supportgenie.schemas import ConfidenceLevel, IssueCategory
from supportgenie.ui.helpers import (
    backend_setup_message,
    compose_issue_summary,
    sentiment_for,
    urgency_for,
)


def test_compose_issue_summary_with_subject_and_description() -> None:
    assert compose_issue_summary("Sync fails", "Token request returns 401") == "Sync fails: Token request returns 401"


def test_compose_issue_summary_with_single_value() -> None:
    assert compose_issue_summary("  Subject only  ", " ") == "Subject only"


def test_backend_setup_message_demo_mode() -> None:
    message = backend_setup_message(
        demo_mode=True,
        azure_ai_foundry_endpoint=None,
        azure_ai_foundry_api_key=None,
        azure_ai_search_endpoint=None,
        azure_ai_search_api_key=None,
        azure_ai_search_index_name=None,
        sql_server_connection_string=None,
    )
    assert "Demo mode is enabled" in message


def test_backend_setup_message_live_mode_missing_values() -> None:
    message = backend_setup_message(
        demo_mode=False,
        azure_ai_foundry_endpoint="https://example",
        azure_ai_foundry_api_key=None,
        azure_ai_search_endpoint=None,
        azure_ai_search_api_key="key",
        azure_ai_search_index_name="index",
        sql_server_connection_string=None,
    )
    assert "AZURE_AI_FOUNDRY_API_KEY" in message
    assert "AZURE_AI_SEARCH_ENDPOINT" in message
    assert "SQL_SERVER_CONNECTION_STRING" in message


def test_sentiment_and_urgency_mappings() -> None:
    assert sentiment_for(IssueCategory.CHANGE_REQUEST) == "Neutral"
    assert sentiment_for(IssueCategory.PRODUCT_BUG) == "Negative"
    assert urgency_for(IssueCategory.PRODUCT_BUG, ConfidenceLevel.HIGH) == "High"
    assert urgency_for(IssueCategory.EXPECTED_BEHAVIOUR, ConfidenceLevel.HIGH) == "Medium-High"
