from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/.env, found no matter which folder the server is started from.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    ENV: str = "dev"
    DATABASE_URL: str = ""
    GROQ_API_KEY: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""
    SESSION_SECRET: str = ""
    PWA_ORIGIN:str =""
    ALLOWED_GOOGLE_EMAILS: str = ""
    


@lru_cache
def get_settings() -> Settings:
    return Settings()
