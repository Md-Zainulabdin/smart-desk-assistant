from pathlib import Path
from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from yoyo import get_backend, read_migrations

from app.config import settings

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

pool = ConnectionPool(
    settings.database_url,
    kwargs={"row_factory": dict_row},
    min_size=1,
    max_size=5,
    open=False,
)


def get_db() -> Iterator[psycopg.Connection]:
    with pool.connection() as conn:
        yield conn


def run_migrations() -> None:
    backend = get_backend(settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1))
    migrations = read_migrations(str(MIGRATIONS_DIR))
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))
