from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/dazi"

    # LLM (OpenAI-compatible chat completion API)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    # Embedding (OpenAI-compatible embedding API)
    embedding_provider: str = "openai"  # "minimax" adds type param
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Crypto
    contact_encryption_key: str = ""  # 32-byte hex key for AES-256

    # Rate limiting
    rate_limit_backend: str = "memory"  # "memory" or "db"

    # Auth
    auth_timestamp_tolerance_seconds: int = 300  # 5 minutes

    model_config = {"env_prefix": "DAZI_", "env_file": ".env"}


settings = Settings()
