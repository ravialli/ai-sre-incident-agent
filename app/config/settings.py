from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mimir_base_url: str = "http://127.0.0.1:8081/prometheus"

    class Config:
        env_file = ".env"


settings = Settings()