from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    openai_api_key: str
    openai_model: str = "gpt-5"
    openai_base_url: str | None = None  # e.g. https://api.groq.com/openai/v1 for Groq


    # Database
    database_url: str
    sync_database_url: str

    # Agent behavior
    max_steps: int = 25
    headless: bool = True
    nav_timeout_ms: int = 30000
    screenshot_dir: str = "./screenshots"

    # App
    app_env: str = "dev"
    log_level: str = "INFO"


settings = Settings()