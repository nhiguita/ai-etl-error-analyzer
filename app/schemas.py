"""Pydantic models for the API and for the LLM structured output."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ErrorType(StrEnum):
    """Mirrors docs/ERROR_TAXONOMY.md."""

    DATABASE_CONSTRAINT = "DATABASE_CONSTRAINT"
    INVALID_VALUE = "INVALID_VALUE"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    DATABASE_CONNECTION = "DATABASE_CONNECTION"
    AUTHENTICATION = "AUTHENTICATION"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class LLMDiagnosis(BaseModel):
    """The JSON the model must return; its schema is sent to Ollama as `format`."""

    error_type: ErrorType
    severity: Severity
    probable_cause: str = Field(min_length=1, max_length=300)
    recommendation: str = Field(min_length=1, max_length=500)


class LogAnalysisRequest(BaseModel):
    log_text: str = Field(min_length=1, max_length=200_000, description="Raw Apache Hop log or error excerpt.")
    pipeline: str | None = Field(default=None, max_length=100, description="Overrides the name found in the log.")


class LogAnalysisResponse(BaseModel):
    analysis_id: int
    created_at: datetime
    pipeline: str | None
    failed_transform: str | None
    root_error: str | None
    error_type: ErrorType
    severity: Severity
    probable_cause: str
    recommendation: str
    model: str
