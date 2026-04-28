import httpx
from app.config import settings

_http_client: httpx.AsyncClient | None = None


async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def compute_embedding(text: str) -> list[float]:
    """Compute embedding for a text string."""
    if settings.embedding_provider == "openai":
        return await _openai_embedding(text)
    return await _minimax_embedding(text)


async def _minimax_embedding(text: str) -> list[float]:
    """Call MiniMax embedding API."""
    client = await get_http_client()
    resp = await client.post(
        f"{settings.minimax_base_url}/embeddings",
        headers={
            "Authorization": f"Bearer {settings.minimax_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.embedding_model,
            "input": [text],
            "type": "db",  # "db" for stored docs, "query" for search queries
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0]["embedding"]


async def compute_query_embedding(text: str) -> list[float]:
    """Compute embedding for a search query (may use different type hint)."""
    if settings.embedding_provider == "openai":
        return await _openai_embedding(text)
    # MiniMax distinguishes "query" vs "db" type
    client = await get_http_client()
    resp = await client.post(
        f"{settings.minimax_base_url}/embeddings",
        headers={
            "Authorization": f"Bearer {settings.minimax_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.embedding_model,
            "input": [text],
            "type": "query",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0]["embedding"]


async def _openai_embedding(text: str) -> list[float]:
    """Fallback: OpenAI text-embedding-3-small."""
    client = await get_http_client()
    resp = await client.post(
        "https://api.openai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {settings.embedding_api_key}",
            "Content-Type": "application/json",
        },
        json={"model": "text-embedding-3-small", "input": text},
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0]["embedding"]
