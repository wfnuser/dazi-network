import json
from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import require_did_auth
from app.db import get_pool
from app.models import SearchRequest, SearchResponse, CandidateResult, ErrorResponse
from app.llm import parse_search_intent
from app.embedding import compute_query_embedding
from app.rate_limit import rate_limiter, RateLimitExceeded, RATE_LIMITS

router = APIRouter(tags=["search"])

# Mapping from dimension name to DB column
DIM_TO_COLUMN = {
    "summary": "emb_summary",
    "personality": "emb_personality",
    "interests": "emb_interests",
    "values": "emb_values",
    "lifestyle": "emb_lifestyle",
}

MAX_CANDIDATES = 30


@router.post(
    "/search",
    response_model=SearchResponse,
    responses={404: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def search_candidates(
    body: SearchRequest,
    response: Response,
    did: str = Depends(require_did_auth),
):
    # Rate limit
    try:
        rate_limiter.check(did, "search", **RATE_LIMITS["search"])
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
                detail={
                    "error": "not_found",
                    "message": "You must create a profile first (POST /profile)",
                },
            )

        # Parse intent via LLM
        parsed = await parse_search_intent(body.intent)
        filters = parsed["filters"]
        dimensions = parsed["dimensions"]
        query_text = parsed["query_embedding_text"]

        # Compute query embedding
        query_emb = await compute_query_embedding(query_text)
        query_emb_str = "[" + ",".join(str(x) for x in query_emb) + "]"

        # Build WHERE clause for hard filters
        where_clauses = ["did != $1"]
        params: list = [did]
        param_idx = 2

        if "city" in filters:
            where_clauses.append(f"city = ${param_idx}")
            params.append(filters["city"])
            param_idx += 1

        if "gender" in filters:
            where_clauses.append(f"gender = ${param_idx}")
            params.append(filters["gender"])
            param_idx += 1

        if "birth_year_min" in filters:
            where_clauses.append(f"birth_year >= ${param_idx}")
            params.append(int(filters["birth_year_min"]))
            param_idx += 1

        if "birth_year_max" in filters:
            where_clauses.append(f"birth_year <= ${param_idx}")
            params.append(int(filters["birth_year_max"]))
            param_idx += 1

        where_sql = " AND ".join(where_clauses)

        # Build ORDER BY: average cosine distance across selected dimensions
        # pgvector: <=> is cosine distance (1 - cosine_similarity), lower = more similar
        if len(dimensions) == 1:
            col = DIM_TO_COLUMN[dimensions[0]]
            order_sql = f"{col} <=> '{query_emb_str}'::vector"
        else:
            parts = [f"({DIM_TO_COLUMN[d]} <=> '{query_emb_str}'::vector)" for d in dimensions]
            order_sql = "(" + " + ".join(parts) + f") / {len(parts)}"

        query = f"""
            SELECT nickname, tags
            FROM profiles
            WHERE {where_sql}
            ORDER BY {order_sql} ASC
            LIMIT {MAX_CANDIDATES}
        """

        rows = await conn.fetch(query, *params)

    candidates = []
    for row in rows:
        tags = json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"]
        candidates.append(CandidateResult(nickname=row["nickname"], tags=tags))

    # Set rate limit headers
    config = RATE_LIMITS["search"]
    info = rate_limiter.get_info(did, "search", **config)
    response.headers["X-RateLimit-Limit"] = str(info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    response.headers["X-RateLimit-Reset"] = info["reset"]

    return SearchResponse(candidates=candidates, total=len(candidates))
