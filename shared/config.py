"""Shared configuration loaded from .env / environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings. All values can be overridden via environment variables."""

    # LLM credentials (required by Agent A for transaction categorisation)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-20b"

    # Agent ports
    agent_a_port: int = 8001
    agent_b_port: int = 8002

    # Pack directory (input data)
    pack_dir: str = "./pack"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
