"""Tests for the database configuration (no real connection)."""

import pytest

from app.db import database_url
from app.models import LogAnalysis


def test_database_url_from_env(monkeypatch):
    monkeypatch.setenv("ETL_DB_HOST", "db.local")
    monkeypatch.setenv("ETL_DB_PORT", "5433")
    monkeypatch.setenv("ETL_DB_USER", "analyzer")
    monkeypatch.setenv("ETL_DB_NAME", "analyzer_db")
    monkeypatch.setenv("ETL_DB_PASSWORD", "fake-secret")

    url = database_url()

    assert url.drivername == "postgresql+psycopg"
    assert (url.host, url.port, url.username, url.database) == ("db.local", 5433, "analyzer", "analyzer_db")
    assert url.password == "fake-secret"
    assert "fake-secret" not in str(url)


def test_database_url_requires_password(monkeypatch):
    monkeypatch.delenv("ETL_DB_PASSWORD", raising=False)
    with pytest.raises(KeyError):
        database_url()


def test_model_matches_sql_table():
    table = LogAnalysis.__table__
    assert table.fullname == "analyzer.log_analyses"
    assert {c.name for c in table.columns} == {
        "analysis_id", "created_at", "pipeline", "failed_transform", "root_error", "error_type",
        "severity", "probable_cause", "recommendation", "model", "log_text",
    }
