"""SQLAlchemy models. The tables are created by sql/03_analyses.sql."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LogAnalysis(Base):
    __tablename__ = "log_analyses"
    __table_args__ = {"schema": "analyzer"}

    analysis_id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    pipeline: Mapped[str | None] = mapped_column(String(300))
    failed_transform: Mapped[str | None] = mapped_column(String(300))
    root_error: Mapped[str | None] = mapped_column(String(300))
    error_type: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(10))
    probable_cause: Mapped[str] = mapped_column(String(300))
    recommendation: Mapped[str] = mapped_column(String(500))
    model: Mapped[str] = mapped_column(String(100))
    log_text: Mapped[str] = mapped_column(Text)
