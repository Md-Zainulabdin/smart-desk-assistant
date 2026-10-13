from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    session_secret: str
    database_url: str
    pwa_origin: str = "http://localhost:3000"
    cookie_secure: bool = False


settings = Settings()
