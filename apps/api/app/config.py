from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
    app_env: str = "development"
    app_base_url: str = "http://localhost:3000"
    database_url: str = "postgresql+asyncpg://applypilot:applypilot_dev@localhost:5432/applypilot"
    redis_url: str = "redis://localhost:6379/0"
    credential_encryption_key: str = ""
    local_storage_path: str = "./uploads"
    max_upload_mb: int = 20
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
