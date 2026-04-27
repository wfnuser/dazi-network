from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import require_did_auth
from app.db import get_pool
from app.models import InterestRequest, InterestResponse, ContactInfo, ErrorResponse
from app.crypto import decrypt_contact
from app.rate_limit import rate_limiter, RateLimitExceeded, RATE_LIMITS

router = APIRouter(tags=["interest"])


@router.post(
    "/interest",
    response_model=InterestResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def express_interest(
    body: InterestRequest,
    response: Response,
    did: str = Depends(require_did_auth),
):
    # Rate limit
    try:
        rate_limiter.check(did, "interest", **RATE_LIMITS["interest"])
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "retry_after": e.retry_after},
        )

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify caller has a profile
        caller = await conn.fetchrow(
            "SELECT did, nickname FROM profiles WHERE did = $1", did
        )
        if not caller:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "You must create a profile first"},
            )

        # Find target by nickname
        target = await conn.fetchrow(
            "SELECT did, nickname, contact_type, contact_value FROM profiles WHERE nickname = $1",
            body.target_nickname,
        )
        if not target:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"User '{body.target_nickname}' not found",
                },
            )

        target_did = target["did"]

        # Cannot interest self
        if target_did == did:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_error",
                    "message": "Cannot express interest in yourself",
                },
            )

        # Check for duplicate
        existing = await conn.fetchrow(
            "SELECT id FROM interests WHERE from_did = $1 AND to_did = $2",
            did, target_did,
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "conflict",
                    "message": "Already expressed interest in this person",
                },
            )

        now = datetime.now(timezone.utc)

        # Check if target already expressed interest in caller (mutual match)
        reverse = await conn.fetchrow(
            "SELECT id, status FROM interests WHERE from_did = $1 AND to_did = $2 AND status = 'pending'",
            target_did, did,
        )

        if reverse:
            # Mutual match!
            await conn.execute(
                "UPDATE interests SET status = 'matched', matched_at = $1 WHERE id = $2",
                now, reverse["id"],
            )
            await conn.execute(
                """INSERT INTO interests (from_did, to_did, status, created_at, matched_at)
                   VALUES ($1, $2, 'matched', $3, $3)""",
                did, target_did, now,
            )

            # Decrypt target's contact
            contact_value = decrypt_contact(target["contact_value"])

            # Set rate limit headers
            config = RATE_LIMITS["interest"]
            info = rate_limiter.get_info(did, "interest", **config)
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
            response.headers["X-RateLimit-Reset"] = info["reset"]

            return InterestResponse(
                status="matched",
                contact=ContactInfo(type=target["contact_type"], value=contact_value),
                message="Mutual match! Here's their contact info.",
            )
        else:
            # Pending
            await conn.execute(
                """INSERT INTO interests (from_did, to_did, status, created_at)
                   VALUES ($1, $2, 'pending', $3)""",
                did, target_did, now,
            )

            config = RATE_LIMITS["interest"]
            info = rate_limiter.get_info(did, "interest", **config)
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
            response.headers["X-RateLimit-Reset"] = info["reset"]

            return InterestResponse(
                status="pending",
                contact=None,
                message="Interest sent. You'll be notified when they respond.",
            )
