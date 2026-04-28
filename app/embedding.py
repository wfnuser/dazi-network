import httpx
from app.config import settings

_http_client: httpx.AsyncClient | None = None


async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def _call_embedding_api(text: str | list[str], **extra) -> list[float]:
    """Call embedding API. Works with OpenAI-compatible endpoints (OpenAI, MiniMax, etc.)."""
    client = await get_http_client()
    api_key = settings.embedding_api_key or settings.minimax_api_key
    resp = await client.post(
        f"{settings.embedding_base_url}/embeddings",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.embedding_model,
            "input": text if isinstance(text, list) else [text],
            **extra,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0]["embedding"]


async def compute_embedding(text: str) -> list[float]:
    """Compute embedding for storing (document side)."""
    extra = {"type": "db"} if settings.embedding_provider == "minimax" else {}
    return await _call_embedding_api(text, **extra)


async def compute_query_embedding(text: str) -> list[float]:
    """Compute embedding for search query."""
    extra = {"type": "query"} if settings.embedding_provider == "minimax" else {}
    return await _call_embedding_api(text, **extra)
