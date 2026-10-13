"""FastAPI application: POST /api/v1/logs/analyze."""

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_session
from app.llm import InvalidDiagnosisError, LLMAnalyzer, LLMUnavailableError
from app.models import LogAnalysis
from app.parser import parse_log
from app.schemas import LogAnalysisRequest, LogAnalysisResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="AI ETL Error Analyzer", version="0.1.0")


@lru_cache
def get_analyzer() -> LLMAnalyzer:
    return LLMAnalyzer.from_env()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/logs/analyze", response_model=LogAnalysisResponse)
def analyze_log(
    request: LogAnalysisRequest,
    analyzer: Annotated[LLMAnalyzer, Depends(get_analyzer)],
    session: Annotated[Session, Depends(get_session)],
) -> LogAnalysisResponse:
    parsed = parse_log(request.log_text)
    if not parsed.has_error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No error found in the log.")

    pipeline = request.pipeline or parsed.pipeline
    try:
        diagnosis = analyzer.diagnose(parsed, pipeline)
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The LLM service is unavailable.") from exc
    except InvalidDiagnosisError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The LLM returned an invalid diagnosis.") from exc

    record = LogAnalysis(
        pipeline=pipeline,
        failed_transform=parsed.failed_transform,
        root_error=parsed.root_error,
        error_type=diagnosis.error_type.value,
        severity=diagnosis.severity.value,
        probable_cause=diagnosis.probable_cause,
        recommendation=diagnosis.recommendation,
        model=analyzer.model,
        log_text=request.log_text,
    )
    try:
        session.add(record)
        session.commit()
        session.refresh(record)
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception("Could not store the analysis")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The analysis could not be stored.") from exc

    return LogAnalysisResponse(
        analysis_id=record.analysis_id,
        created_at=record.created_at,
        pipeline=record.pipeline,
        failed_transform=record.failed_transform,
        root_error=record.root_error,
        error_type=diagnosis.error_type,
        severity=diagnosis.severity,
        probable_cause=record.probable_cause,
        recommendation=record.recommendation,
        model=record.model,
    )
