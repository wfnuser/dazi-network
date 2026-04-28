from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import require_did_auth
from app.db import get_pool
from app.models import InterestRequest, InterestResponse, ContactInfo, ErrorResponse
from app.crypto import decrypt_contact
from app.rate_limit import rate_limiter, RateLimitExceeded, RATE_LIMITS

router = APIRouter(tags=["interest"])


def _set_rate_headers(response: Response, did: str):
    config = RATE_LIMITS["interest"]
    info = rate_limiter.get_info(did, "interest", **config)
    response.headers["X-RateLimit-Limit"] = str(info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    response.headers["X-RateLimit-Reset"] = info["reset"]


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

        # Cannot target self
        if target_did == did:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_error",
                    "message": "Cannot express interest in yourself",
                },
            )

        # === DECLINE ===
        if body.action == "decline":
            # Find incoming interest from target to me
            incoming = await conn.fetchrow(
                "SELECT id, status FROM interests WHERE from_did = $1 AND to_did = $2 AND status = 'pending'",
                target_did, did,
            )
            if not incoming:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "not_found",
                        "message": f"No pending interest from '{body.target_nickname}' to decline",
                    },
                )
            await conn.execute(
                "UPDATE interests SET status = 'declined' WHERE id = $1",
                incoming["id"],
            )
            _set_rate_headers(response, did)
            return InterestResponse(
                status="declined",
                contact=None,
                message=f"Declined interest from '{body.target_nickname}'.",
            )

        # === WITHDRAW ===
        if body.action == "withdraw":
            # Find my outgoing interest to target
            outgoing = await conn.fetchrow(
                "SELECT id, status FROM interests WHERE from_did = $1 AND to_did = $2 AND status = 'pending'",
                did, target_did,
            )
            if not outgoing:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "not_found",
                        "message": f"No pending interest to '{body.target_nickname}' to withdraw",
                    },
                )
            await conn.execute("DELETE FROM interests WHERE id = $1", outgoing["id"])
            _set_rate_headers(response, did)
            return InterestResponse(
                status="declined",
                contact=None,
                message=f"Withdrew interest in '{body.target_nickname}'.",
            )

        # === ACCEPT (default) ===
        # Check for duplicate outgoing
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
                """INSERT INTO interests (from_did, to_did, message, status, created_at, matched_at)
                   VALUES ($1, $2, $3, 'matched', $4, $4)""",
                did, target_did, body.message, now,
            )

            contact_value = decrypt_contact(target["contact_value"])
            _set_rate_headers(response, did)
            return InterestResponse(
                status="matched",
                contact=ContactInfo(type=target["contact_type"], value=contact_value),
                message="Mutual match! Here's their contact info.",
            )
        else:
            # Pending
            await conn.execute(
                """INSERT INTO interests (from_did, to_did, message, status, created_at)
                   VALUES ($1, $2, $3, 'pending', $4)""",
                did, target_did, body.message, now,
            )
            _set_rate_headers(response, did)
            return InterestResponse(
                status="pending",
                contact=None,
                message="Interest sent. You'll be notified when they respond.",
            )
