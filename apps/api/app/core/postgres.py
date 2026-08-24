from __future__ import annotations

import logging
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.core.config import get_settings
from app.db_url import sanitize_db_url


logger = logging.getLogger(__name__)
settings = get_settings()

try:
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - psycopg-pool missing in lean envs
    ConnectionPool = None

_pool = None


def _get_pool():
    """Lazily create the shared pool. Returns None when psycopg-pool is not
    installed, in which case callers fall back to one-off connections."""
    global _pool
    if _pool is None and ConnectionPool is not None:
        _pool = ConnectionPool(
            sanitize_db_url(settings.direct_url or settings.database_url),
            min_size=1,
            max_size=8,
            open=True,
            kwargs={"row_factory": dict_row},
        )
        logger.info("psycopg connection pool opened (min=1 max=8)")
    return _pool


@contextmanager
def get_connection():
    """Yield a dict-row connection, pooled when psycopg-pool is available.

    Used by the sync side-channel (Celery tasks, usage recorder, agent
    stages) — pooling here stops connection-per-call churn against the
    managed Postgres instance.
    """
    pool = _get_pool()
    if pool is not None:
        with pool.connection() as conn:
            yield conn
        return

    url = sanitize_db_url(settings.direct_url or settings.database_url)
    connection = psycopg.connect(url, row_factory=dict_row)
    try:
        yield connection
    finally:
        connection.close()