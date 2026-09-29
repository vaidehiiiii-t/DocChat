import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(Path(__file__).resolve().parent.parent, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    FLASK_ENV: str = "development"
    SECRET_KEY: str = "change-me-secret-key-at-least-32-chars-long"
    JWT_SECRET_KEY: str = "change-me-jwt-secret-key-at-least-32-chars-long"
    JWT_ACCESS_MINUTES: int = 60

    DATABASE_URL: str = "mysql+pymysql://docchat:docchat@localhost:3306/docchat"
    TEST_DATABASE_URL: str = "sqlite:///:memory:"

    UPLOAD_DIR: str = "./storage/uploads"
    CHROMA_DIR: str = "./storage/chroma"
    MAX_UPLOAD_MB: int = 20
    ALLOWED_EXTENSIONS: str = "pdf,txt,md"

    CHROMA_API_KEY: str = ""
    CHROMA_TENANT: str = ""
    CHROMA_DATABASE: str = "Docchat"

    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150

    TOP_K: int = 5
    MAX_DISTANCE: float = 0.55
    HISTORY_TURNS: int = 6

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "google/gemma-4-31b-it:free"
    LLM_FALLBACK_MODELS: str = "nvidia/nemotron-3-super:free"
    LLM_MAX_TOKENS: int = 1000
    LLM_TEMPERATURE: float = 0.2
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_MAX_RETRIES: int = 3
    LLM_GLOBAL_RPM: int = 18
    LLM_DAILY_SOFT_LIMIT: int = 45
    ALLOW_PAID_MODELS: bool = False
    APP_NAME: str = "DocChat"

    FRONTEND_ORIGIN: str = "http://localhost:5173"

    @property
    def max_content_length(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def allowed_extensions_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",") if ext.strip()}

    @property
    def fallback_models_list(self) -> list[str]:
        return [m.strip() for m in self.LLM_FALLBACK_MODELS.split(",") if m.strip()]


class Config:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    def apply_to_flask(self, app):
        s = self.settings
        app.config["SECRET_KEY"] = s.SECRET_KEY
        app.config["JWT_SECRET_KEY"] = s.JWT_SECRET_KEY
        app.config["JWT_ACCESS_TOKEN_EXPIRES"] = s.JWT_ACCESS_MINUTES * 60
        app.config["SQLALCHEMY_DATABASE_URI"] = s.DATABASE_URL
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        app.config["MAX_CONTENT_LENGTH"] = s.max_content_length
        app.config["UPLOAD_DIR"] = s.UPLOAD_DIR
        app.config["CHROMA_DIR"] = s.CHROMA_DIR
        app.config["CHROMA_API_KEY"] = s.CHROMA_API_KEY
        app.config["CHROMA_TENANT"] = s.CHROMA_TENANT
        app.config["CHROMA_DATABASE"] = s.CHROMA_DATABASE
        app.config["FRONTEND_ORIGIN"] = s.FRONTEND_ORIGIN
        app.config["DOCCHAT_SETTINGS"] = s


class TestConfig(Config):
    def __init__(self):
        super().__init__()
        # In test mode, override DB to SQLite in-memory
        self.settings.DATABASE_URL = self.settings.TEST_DATABASE_URL

    def apply_to_flask(self, app):
        super().apply_to_flask(app)
        from sqlalchemy.pool import StaticPool

        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
