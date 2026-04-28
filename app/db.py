import asyncpg
from app.config import settings

pool: asyncpg.Pool | None = None


async def init_pool():
    global pool
    pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)


async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None


async def get_pool() -> asyncpg.Pool:
    assert pool is not None, "Database pool not initialized"
    return pool


async def init_db():
    """Create tables and extensions. Idempotent."""
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                did             TEXT PRIMARY KEY,
                nickname        TEXT NOT NULL UNIQUE,
                birth_year      INTEGER NOT NULL,
                gender          TEXT NOT NULL CHECK (gender IN ('M', 'F', 'O')),
                city            TEXT NOT NULL,
                tags            JSONB NOT NULL,
                contact_type    TEXT NOT NULL CHECK (contact_type IN ('wechat', 'telegram', 'twitter', 'jike', 'email')),
                contact_value   BYTEA NOT NULL,
                ai_summary      TEXT NOT NULL DEFAULT '',
                ai_personality  TEXT NOT NULL DEFAULT '',
                ai_interests    TEXT NOT NULL DEFAULT '',
                ai_values       TEXT NOT NULL DEFAULT '',
                ai_lifestyle    TEXT NOT NULL DEFAULT '',
                emb_summary     vector(1536),
                emb_personality vector(1536),
                emb_interests   vector(1536),
                emb_values      vector(1536),
                emb_lifestyle   vector(1536),
                version         INTEGER NOT NULL DEFAULT 1,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS interests (
                id              SERIAL PRIMARY KEY,
                from_did        TEXT NOT NULL REFERENCES profiles(did) ON DELETE CASCADE,
                to_did          TEXT NOT NULL REFERENCES profiles(did) ON DELETE CASCADE,
                message         TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'matched', 'declined')),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                matched_at      TIMESTAMPTZ,
                UNIQUE(from_did, to_did)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                did             TEXT NOT NULL,
                endpoint        TEXT NOT NULL,
                window_start    TIMESTAMPTZ NOT NULL,
                count           INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (did, endpoint, window_start)
            )
        """)

        # Indexes for search performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_city ON profiles (city)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_gender ON profiles (gender)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_birth_year ON profiles (birth_year)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_interests_to_did ON interests (to_did)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_interests_from_did ON interests (from_did)")
