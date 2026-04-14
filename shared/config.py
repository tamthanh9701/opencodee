from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    litellm_api_key: str = ""
    litellm_base_url: str = "http://localhost:4000"
    litellm_model: str = "openai/gpt-4o"
    figma_api_token: str = ""
    db_path: Path = Path("claw_pipeline.db")
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_backoff_factor: float = 2.0
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()