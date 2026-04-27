import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import require_did_auth
from app.db import get_pool
from app.models import ProfileRequest, ProfileResponse, DeleteResponse, ErrorResponse
from app.crypto import encrypt_contact
from app.llm import generate_ai_extracted
from app.embedding import compute_embedding
from app.rate_limit import rate_limiter, RateLimitExceeded, RATE_LIMITS

router = APIRouter(tags=["profile"])


def _format_vector(emb: list[float]) -> str:
    """Format embedding list as pgvector string literal."""
    return "[" + ",".join(f"{x:.8f}" for x in emb) + "]"


def _rate_limit_headers(did: str, endpoint: str) -> dict:
    config = RATE_LIMITS[endpoint]
    info = rate_limiter.get_info(did, endpoint, **config)
    return {
        "X-RateLimit-Limit": str(info["limit"]),
        "X-RateLimit-Remaining": str(info["remaining"]),
        "X-RateLimit-Reset": info["reset"],
    }


@router.post(
    "/profile",
    response_model=ProfileResponse,
    responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def create_or_update_profile(
    body: ProfileRequest,
    response: Response,
    did: str = Depends(require_did_auth),
):
    # Rate limit
    try:
        rate_limiter.check(did, "profile", **RATE_LIMITS["profile"])
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "retry_after": e.retry_after},
        )

    pool = await get_pool()

    # Encrypt contact
    encrypted_contact = encrypt_contact(body.contact.value)

    # Generate ai_extracted via LLM
    ai_extracted = await generate_ai_extracted(body.tags)

    # Compute 5 embeddings
    emb_summary = await compute_embedding(ai_extracted["summary"])
    emb_personality = await compute_embedding(ai_extracted["personality"])
    emb_interests = await compute_embedding(ai_extracted["interests"])
    emb_values = await compute_embedding(ai_extracted["values"])
    emb_lifestyle = await compute_embedding(ai_extracted["lifestyle"])

    now = datetime.now(timezone.utc).isoformat()
    tags_json = json.dumps(body.tags, ensure_ascii=False)

    async with pool.acquire() as conn:
        # Check if profile exists
        existing = await conn.fetchrow("SELECT version FROM profiles WHERE did = $1", did)

        if existing:
            new_version = existing["version"] + 1
            await conn.execute(
                """
                UPDATE profiles SET
                    nickname = $2, age = $3, gender = $4, city = $5,
                    tags = $6, contact_type = $7, contact_value = $8,
                    ai_summary = $9, ai_personality = $10, ai_interests = $11,
                    ai_values = $12, ai_lifestyle = $13,
                    emb_summary = $14::vector, emb_personality = $15::vector,
                    emb_interests = $16::vector, emb_values = $17::vector,
                    emb_lifestyle = $18::vector,
                    version = $19, updated_at = $20
                WHERE did = $1
                """,
                did, body.nickname, body.basic.age, body.basic.gender, body.basic.city,
                tags_json, body.contact.type, encrypted_contact,
                ai_extracted["summary"], ai_extracted["personality"],
                ai_extracted["interests"], ai_extracted["values"], ai_extracted["lifestyle"],
                _format_vector(emb_summary), _format_vector(emb_personality),
                _format_vector(emb_interests), _format_vector(emb_values),
                _format_vector(emb_lifestyle),
                new_version, now,
            )
            status_code = 200
            version = new_version
            created_at = now
        else:
            version = 1
            await conn.execute(
                """
                INSERT INTO profiles (
                    did, nickname, age, gender, city,
                    tags, contact_type, contact_value,
                    ai_summary, ai_personality, ai_interests, ai_values, ai_lifestyle,
                    emb_summary, emb_personality, emb_interests, emb_values, emb_lifestyle,
                    version, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8,
                    $9, $10, $11, $12, $13,
                    $14::vector, $15::vector, $16::vector, $17::vector, $18::vector,
                    $19, $20, $20
                )
                """,
                did, body.nickname, body.basic.age, body.basic.gender, body.basic.city,
                tags_json, body.contact.type, encrypted_contact,
                ai_extracted["summary"], ai_extracted["personality"],
                ai_extracted["interests"], ai_extracted["values"], ai_extracted["lifestyle"],
                _format_vector(emb_summary), _format_vector(emb_personality),
                _format_vector(emb_interests), _format_vector(emb_values),
                _format_vector(emb_lifestyle),
                version, now,
            )
            status_code = 201
            created_at = now

    # Set rate limit headers
    for k, v in _rate_limit_headers(did, "profile").items():
        response.headers[k] = v

    response.status_code = status_code
    return ProfileResponse(did=did, nickname=body.nickname, version=version, created_at=created_at)


@router.delete(
    "/profile",
    response_model=DeleteResponse,
    responses={404: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def delete_profile(
    response: Response,
    did: str = Depends(require_did_auth),
):
    try:
        rate_limiter.check(did, "delete_profile", **RATE_LIMITS["delete_profile"])
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "retry_after": e.retry_after},
        )

    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT did FROM profiles WHERE did = $1", did)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "Profile not found"},
            )
        # CASCADE deletes interests too
        await conn.execute("DELETE FROM interests WHERE from_did = $1 OR to_did = $1", did)
        await conn.execute("DELETE FROM rate_limits WHERE did = $1", did)
        await conn.execute("DELETE FROM profiles WHERE did = $1", did)

    return DeleteResponse(message="Profile and all associated data deleted.")
