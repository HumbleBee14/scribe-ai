from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# multimodal-prox-challenge/ is the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
FILES_DIR = PROJECT_ROOT / "files"
PRODUCTS_DIR = DATA_DIR / "products"


class Settings(BaseSettings):
    # Required
    anthropic_api_key: str = ""

    # Model (renamed from model_name to avoid Pydantic protected namespace warning)
    llm_model: str = "claude-sonnet-4-6"

    # Database
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'local.db'}"
    app_env: str = "development"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"

    # Paths
    knowledge_dir: str = str(KNOWLEDGE_DIR)
    files_dir: str = str(FILES_DIR)
    products_dir: str = str(PRODUCTS_DIR)
    default_product_id: str = "vulcan-omnipro-220"

    # Feature flags
    enable_vector_search: bool = False

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
