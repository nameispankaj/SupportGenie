from supportgenie.schemas import ConfidenceLevel, IssueCategory, TicketAnalysisResponse


def compose_issue_summary(subject: str, description: str) -> str:
    if subject.strip() and description.strip():
        return f"{subject.strip()}: {description.strip()}"
    return subject.strip() or description.strip()


def backend_setup_message(
    *,
    demo_mode: bool,
    azure_ai_foundry_endpoint: str | None,
    azure_ai_foundry_api_key: str | None,
    azure_ai_search_endpoint: str | None,
    azure_ai_search_api_key: str | None,
    azure_ai_search_index_name: str | None,
    sql_server_connection_string: str | None,
) -> str:
    if demo_mode:
        return "Demo mode is enabled. Analysis uses synthetic ticket data without Azure AI Search or SQL Server."

    missing = []
    required = {
        "AZURE_AI_FOUNDRY_ENDPOINT": azure_ai_foundry_endpoint,
        "AZURE_AI_FOUNDRY_API_KEY": azure_ai_foundry_api_key,
        "AZURE_AI_SEARCH_ENDPOINT": azure_ai_search_endpoint,
        "AZURE_AI_SEARCH_API_KEY": azure_ai_search_api_key,
        "AZURE_AI_SEARCH_INDEX_NAME": azure_ai_search_index_name,
        "SQL_SERVER_CONNECTION_STRING": sql_server_connection_string,
    }
    for name, value in required.items():
        if not value:
            missing.append(name)

    if not missing:
        return "Live mode configuration detected."
    return f"Live mode is selected, but required configuration is missing: {', '.join(missing)}."


def sentiment_for(category: IssueCategory) -> str:
    if category in {IssueCategory.CHANGE_REQUEST, IssueCategory.EXPECTED_BEHAVIOUR}:
        return "Neutral"
    if category == IssueCategory.INSUFFICIENT_INFORMATION:
        return "Uncertain"
    return "Negative"


def urgency_for(category: IssueCategory, confidence: ConfidenceLevel) -> str:
    if category in {IssueCategory.PRODUCT_BUG, IssueCategory.INTEGRATION_ISSUE}:
        return "High"
    if category == IssueCategory.INSUFFICIENT_INFORMATION:
        return "Low"
    if confidence == ConfidenceLevel.HIGH:
        return "Medium-High"
    return "Medium"


def recommended_response_for(analysis: TicketAnalysisResponse) -> str:
    return f"{analysis.recommendation.value}: {analysis.possible_resolution}"
