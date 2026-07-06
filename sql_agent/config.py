"""
Central application configuration.

All tunables (model name, paths, retry limits) live here so that no other
module needs to hardcode values. Reads from environment variables with
sensible local defaults.
"""
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Paths -------------------------------------------------------
    base_dir: Path = Path(__file__).resolve().parent
    upload_dir: Path = base_dir / "uploads"
    data_dir: Path = base_dir / "data"
    sqlite_db_name: str = "hr_dynamic.db"

    # --- LLM (Ollama) --------------------------------------------------
    ollama_model: str = "llama3.1"
    ollama_base_url: str = "http://localhost:11434"
    llm_temperature: float = 0.0

    # --- Agent behaviour -------------------------------------------------
    max_sql_retries: int = 3
    max_sample_rows: int = 5
    relationship_overlap_threshold: float = 0.3  # min value-overlap ratio to infer a FK

    # --- API ---------------------------------------------------------
    app_name: str = "Dynamic SQL Agent"
    app_version: str = "1.0.0"

    @property
    def sqlite_db_path(self) -> Path:
        return self.data_dir / self.sqlite_db_name

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.sqlite_db_path}"

    class Config:
        env_prefix = "SQLAGENT_"


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.data_dir.mkdir(parents=True, exist_ok=True)
