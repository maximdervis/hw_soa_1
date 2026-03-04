"""Подключение к PostgreSQL."""
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2.extras import RealDictCursor

from app.app_config import settings


@contextmanager
def get_db() -> Generator:
    conn = psycopg2.connect(settings.database_url, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
