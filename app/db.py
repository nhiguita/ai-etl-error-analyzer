"""PostgreSQL engine and session, configured from the ETL_DB_* variables."""

import os
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import Session


def database_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("ETL_DB_USER", "etl_analyzer"),
        password=os.environ["ETL_DB_PASSWORD"],
        host=os.getenv("ETL_DB_HOST", "localhost"),
        port=int(os.getenv("ETL_DB_PORT", "5432")),
        database=os.getenv("ETL_DB_NAME", "etl_analyzer_db"),
    )


@lru_cache
def get_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
