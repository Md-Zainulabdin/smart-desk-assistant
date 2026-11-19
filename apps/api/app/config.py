from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    env: str = "dev"
    default_timezone: str = "UTC"
    groq_api_key: str = ""
    tavily_api_key: str = ""

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    # Comma-separated allowlist. Empty means any verified Google account (development only).
    allowed_google_emails: str = ""

    session_secret: str
    session_ttl_days: int = 30
    session_cookie_name: str = "sd_session"
    cookie_secure: bool = False

    database_url: str
    pwa_origin: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"


settings = Settings()
