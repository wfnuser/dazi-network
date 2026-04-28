from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/dazi"

    # MiniMax LLM
    minimax_api_key: str = ""
    minimax_model: str = "MiniMax-Text-01"
    minimax_base_url: str = "https://api.minimax.chat/v1"

    # Embedding
    embedding_provider: str = "minimax"  # "minimax" or "openai"
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

    # Dev mode: use mock LLM/embedding instead of real API
    dev_mode: bool = False

    model_config = {"env_prefix": "DAZI_", "env_file": ".env"}


settings = Settings()
