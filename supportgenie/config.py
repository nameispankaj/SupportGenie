from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SupportGenie"
    api_host: str = Field(default="127.0.0.1", alias="SUPPORTGENIE_API_HOST")
    api_port: int = Field(default=8000, alias="SUPPORTGENIE_API_PORT")
    frontend_origin: str = Field(default="http://127.0.0.1:5500", alias="SUPPORTGENIE_FRONTEND_ORIGIN")

    demo_mode: bool = Field(default=True, alias="SUPPORTGENIE_DEMO_MODE")

    sql_server_host: str | None = Field(default=None, alias="SQL_SERVER_HOST")
    sql_server_port: int = Field(default=1433, alias="SQL_SERVER_PORT")
    sql_server_database: str = Field(default="JotDeskBuddy_Test", alias="SQL_SERVER_DATABASE")
    sql_server_auth_mode: str = Field(default="sql", alias="SQL_SERVER_AUTH_MODE")
    sql_server_username: str | None = Field(default=None, alias="SQL_SERVER_USERNAME")
    sql_server_password: str | None = Field(default=None, alias="SQL_SERVER_PASSWORD")
    sql_server_driver: str = Field(default="ODBC Driver 18 for SQL Server", alias="SQL_SERVER_DRIVER")
    sql_server_trust_server_certificate: bool = Field(default=False, alias="SQL_SERVER_TRUST_SERVER_CERTIFICATE")
    sql_server_encrypt: bool = Field(default=True, alias="SQL_SERVER_ENCRYPT")
    sql_server_connection_timeout: int = Field(default=30, alias="SQL_SERVER_CONNECTION_TIMEOUT")

    tickets_table: str = Field(default="Tickets", alias="SUPPORTGENIE_TICKETS_TABLE")
    ticketchat_table: str = Field(default="TicketChat", alias="SUPPORTGENIE_TICKETCHAT_TABLE")
    ticketfollowups_table: str = Field(default="TicketFollowups", alias="SUPPORTGENIE_TICKETFOLLOWUPS_TABLE")
    ticketemails_table: str = Field(default="TicketEmailMessages", alias="SUPPORTGENIE_TICKETEMAILMESSAGES_TABLE")

    ticket_id_column: str = Field(default="ticket_id", alias="SUPPORTGENIE_TICKET_ID_COLUMN")
    ticket_subject_column: str = Field(default="subject", alias="SUPPORTGENIE_TICKET_SUBJECT_COLUMN")
    ticket_description_column: str = Field(default="description", alias="SUPPORTGENIE_TICKET_DESCRIPTION_COLUMN")
    ticket_status_column: str = Field(default="status", alias="SUPPORTGENIE_TICKET_STATUS_COLUMN")
    ticket_urgency_column: str = Field(default="urgency", alias="SUPPORTGENIE_TICKET_URGENCY_COLUMN")
    ticket_reported_at_column: str = Field(default="report_date", alias="SUPPORTGENIE_TICKET_REPORTED_AT_COLUMN")
    ticket_client_column: str = Field(default="client_name", alias="SUPPORTGENIE_TICKET_CLIENT_COLUMN")
    ticket_project_column: str = Field(default="project_name", alias="SUPPORTGENIE_TICKET_PROJECT_COLUMN")
    ticket_module_column: str = Field(default="module_name", alias="SUPPORTGENIE_TICKET_MODULE_COLUMN")
    ticket_assignee_column: str = Field(default="assigned_to", alias="SUPPORTGENIE_TICKET_ASSIGNEE_COLUMN")
    ticket_report_method_column: str = Field(default="report_method", alias="SUPPORTGENIE_TICKET_REPORT_METHOD_COLUMN")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


settings = Settings()
