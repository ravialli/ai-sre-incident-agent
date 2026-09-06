from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mimir_base_url: str
    loki_base_url: str
    tempo_base_url: str

    loki_tenant_id: str = "prod-app-a"

    request_timeout: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()