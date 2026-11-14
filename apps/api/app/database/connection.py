import logging
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg

from app.config import get_settings

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_pool: asyncpg.Pool | None = None


async def open_pool() -> None:
    """Create the connection pool at startup, so config is read then, not at import."""
    global _pool
    _pool = await asyncpg.create_pool(get_settings().DATABASE_URL, min_size=1, max_size=5)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_connection() -> AsyncIterator[asyncpg.Connection]:
    if _pool is None:
        raise RuntimeError("Database pool is not open")
    async with _pool.acquire() as conn:
        yield conn


async def run_migrations() -> None:
    """Apply pending migrations/*.sql files in filename order, each in its own transaction."""
    conn = await asyncpg.connect(get_settings().DATABASE_URL)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     TEXT PRIMARY KEY,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {row["version"] for row in await conn.fetch("SELECT version FROM schema_migrations")}

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in applied:
                continue
            async with conn.transaction():
                await conn.execute(path.read_text(encoding="utf-8"))
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)", path.stem
                )
            logger.info("Applied migration %s", path.name)
    finally:
        await conn.close()
