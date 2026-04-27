import json
from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import require_did_auth
from app.db import get_pool
from app.models import (
    ConnectionsResponse, PendingConnection, MatchedConnection,
    ContactInfo, ErrorResponse,
)
from app.crypto import decrypt_contact
from app.rate_limit import rate_limiter, RateLimitExceeded, RATE_LIMITS

router = APIRouter(tags=["connections"])


@router.get(
    "/connections",
    response_model=ConnectionsResponse,
    responses={404: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def get_connections(
    response: Response,
    did: str = Depends(require_did_auth),
):
    try:
        rate_limiter.check(did, "connections", **RATE_LIMITS["connections"])
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "retry_after": e.retry_after},
        )

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify caller has a profile
        caller = await conn.fetchrow("SELECT did FROM profiles WHERE did = $1", did)
        if not caller:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "Profile not found"},
            )

        # Pending incoming: others who expressed interest in me, not yet matched
        incoming_rows = await conn.fetch(
            """
            SELECT p.nickname, p.tags
            FROM interests i
            JOIN profiles p ON p.did = i.from_did
            WHERE i.to_did = $1 AND i.status = 'pending'
            ORDER BY i.created_at DESC
            """,
            did,
        )

        # Pending outgoing: I expressed interest, not yet matched
        outgoing_rows = await conn.fetch(
            """
            SELECT p.nickname, p.tags
            FROM interests i
            JOIN profiles p ON p.did = i.to_did
            WHERE i.from_did = $1 AND i.status = 'pending'
            ORDER BY i.created_at DESC
            """,
            did,
        )

        # Matched: mutual matches (I have a matched interest record)
        matched_rows = await conn.fetch(
            """
            SELECT p.nickname, p.tags, p.contact_type, p.contact_value, i.matched_at
            FROM interests i
            JOIN profiles p ON p.did = i.to_did
            WHERE i.from_did = $1 AND i.status = 'matched'
            ORDER BY i.matched_at DESC
            """,
            did,
        )

    def parse_tags(raw):
        if isinstance(raw, str):
            return json.loads(raw)
        return raw

    pending_incoming = [
        PendingConnection(nickname=r["nickname"], tags=parse_tags(r["tags"]))
        for r in incoming_rows
    ]
    pending_outgoing = [
        PendingConnection(nickname=r["nickname"], tags=parse_tags(r["tags"]))
        for r in outgoing_rows
    ]
    matched = [
        MatchedConnection(
            nickname=r["nickname"],
            tags=parse_tags(r["tags"]),
            contact=ContactInfo(
                type=r["contact_type"],
                value=decrypt_contact(r["contact_value"]),
            ),
            matched_at=(
                r["matched_at"].isoformat()
                if hasattr(r["matched_at"], "isoformat")
                else str(r["matched_at"])
            ),
        )
        for r in matched_rows
    ]

    config = RATE_LIMITS["connections"]
    info = rate_limiter.get_info(did, "connections", **config)
    response.headers["X-RateLimit-Limit"] = str(info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    response.headers["X-RateLimit-Reset"] = info["reset"]

    return ConnectionsResponse(
        pending_incoming=pending_incoming,
        pending_outgoing=pending_outgoing,
        matched=matched,
    )
