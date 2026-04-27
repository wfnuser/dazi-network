import os
import pytest
from unittest.mock import AsyncMock, patch

# Use test database
os.environ["DAZI_DATABASE_URL"] = os.environ.get(
    "DAZI_TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/dazi_test"
)
os.environ["DAZI_CONTACT_ENCRYPTION_KEY"] = "a" * 64  # 32-byte hex key for testing
os.environ["DAZI_MINIMAX_API_KEY"] = "test-key"


def make_did_headers(did: str = "did:key:z6MkTestUser1") -> dict:
    """Create valid auth headers for testing. Uses mock signature verification."""
    return {
        "X-DID": did,
        "X-Signature": "dGVzdC1zaWduYXR1cmU=",  # base64("test-signature")
        "X-Timestamp": "2026-04-27T12:00:00Z",
    }


@pytest.fixture
def mock_llm():
    """Mock LLM calls to avoid hitting real API in tests."""
    ai_extracted = {
        "summary": "Test user summary",
        "personality": "Test personality traits",
        "interests": "Test interests",
        "values": "Test values",
        "lifestyle": "Test lifestyle",
    }
    with patch("app.llm.generate_ai_extracted", new_callable=AsyncMock, return_value=ai_extracted):
        yield ai_extracted


@pytest.fixture
def mock_embedding():
    """Mock embedding calls."""
    fake_embedding = [0.1] * 1536
    with patch(
        "app.embedding.compute_embedding", new_callable=AsyncMock, return_value=fake_embedding
    ):
        yield fake_embedding


@pytest.fixture
def mock_auth():
    """Mock auth verification to accept any signature."""
    with patch("app.auth.verify_did_signature", return_value=True):
        yield


@pytest.fixture
def mock_intent_parse():
    """Mock intent parsing."""
    parsed = {
        "filters": {},
        "dimensions": ["personality", "interests"],
        "query_embedding_text": "Test query text",
    }
    with patch("app.llm.parse_search_intent", new_callable=AsyncMock, return_value=parsed):
        yield parsed
