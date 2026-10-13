"""FastAPI application: POST /api/v1/logs/analyze."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status

from app.llm import InvalidDiagnosisError, LLMAnalyzer, LLMUnavailableError
from app.parser import parse_log
from app.schemas import LogAnalysisRequest, LogAnalysisResponse

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

    return LogAnalysisResponse(
        pipeline=pipeline,
        failed_transform=parsed.failed_transform,
        root_error=parsed.root_error,
        model=analyzer.model,
        **diagnosis.model_dump(),
    )
