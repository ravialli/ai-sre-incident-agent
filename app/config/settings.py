from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mimir_base_url: str
    loki_base_url: str
    tempo_base_url: str
    llm_provider: str
    llm_model: str
    anthropic_workspace_id: str | None = None
    embedding_provider: str
    embedding_model: str
    rag_collection_name: str
    rag_persist_directory: str

    loki_tenant_id: str = "prod-app-a"

    request_timeout: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
    )


settings = Settings()