"""Ollama client that returns a validated LLMDiagnosis."""

import logging
import os

import ollama
from pydantic import ValidationError

from app.parser import ParsedLog
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from app.schemas import LLMDiagnosis

logger = logging.getLogger(__name__)

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:4b"


class LLMUnavailableError(Exception):
    """Ollama could not be reached or returned an error."""


class InvalidDiagnosisError(Exception):
    """The model output did not match the LLMDiagnosis schema."""


class LLMAnalyzer:
    def __init__(self, client: ollama.Client, model: str, max_attempts: int = 2):
        self.client = client
        self.model = model
        self.max_attempts = max_attempts

    @classmethod
    def from_env(cls) -> "LLMAnalyzer":
        host = os.getenv("OLLAMA_HOST", DEFAULT_HOST)
        model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        return cls(ollama.Client(host=host), model)

    def diagnose(self, parsed: ParsedLog, pipeline: str | None) -> LLMDiagnosis:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(parsed, pipeline)},
        ]
        last_error: ValidationError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.client.chat(
                    model=self.model,
                    messages=messages,
                    format=LLMDiagnosis.model_json_schema(),
                    think=False,
                    options={"temperature": 0},
                )
            except (ollama.ResponseError, ConnectionError) as exc:
                raise LLMUnavailableError(str(exc)) from exc
            try:
                return LLMDiagnosis.model_validate_json(response.message.content)
            except ValidationError as exc:
                logger.warning("Invalid diagnosis on attempt %d: %s", attempt, exc)
                last_error = exc
        raise InvalidDiagnosisError(str(last_error))
