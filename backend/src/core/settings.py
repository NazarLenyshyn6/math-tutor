from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env", extra="ignore"
    )

    # --- LLM ---
    nvidia_api_key: str
    llm_model_name: str

    # --- Embeddings (HuggingFace) ---
    hf_api_token: str
    embedding_model_name: str

    # --- Elasticsearch ---
    elasticsearch_url: str

    # --- Storage ---
    storage_root_path: str


# Global settings instance for use throughout the application
settings = Settings()
