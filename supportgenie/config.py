from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SupportGenie"
    demo_mode: bool = Field(default=True, alias="SUPPORTGENIE_DEMO_MODE")
    ui_default_tenant_id: str = Field(default="tenant-acme", alias="SUPPORTGENIE_UI_DEFAULT_TENANT_ID")
    ui_default_user_id: str = Field(default="alice", alias="SUPPORTGENIE_UI_DEFAULT_USER_ID")
    azure_ai_foundry_endpoint: str | None = Field(default=None, alias="AZURE_AI_FOUNDRY_ENDPOINT")
    azure_ai_foundry_api_key: str | None = Field(default=None, alias="AZURE_AI_FOUNDRY_API_KEY")
    azure_ai_search_endpoint: str | None = Field(default=None, alias="AZURE_AI_SEARCH_ENDPOINT")
    azure_ai_search_api_key: str | None = Field(default=None, alias="AZURE_AI_SEARCH_API_KEY")
    azure_ai_search_index_name: str | None = Field(default=None, alias="AZURE_AI_SEARCH_INDEX_NAME")
    sql_server_connection_string: str | None = Field(default=None, alias="SQL_SERVER_CONNECTION_STRING")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


settings = Settings()
