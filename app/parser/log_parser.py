"""Extract the key facts from an Apache Hop console log.

The parser is deterministic and does not call the LLM: it reduces a long
Hop log (with Java stack traces) to the pipeline name, the failing transform,
the root error message and a short list of relevant lines that can be sent
to the model as context.
"""

import re
from dataclasses import dataclass, field

MAX_LINE_LENGTH = 300
MAX_ERROR_LINES = 20

# "2026/10/13 09:46:33 - Insert students.0 - ERROR: ..."
HOP_LINE = re.compile(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} - (?P<source>.+?) - (?P<message>.*)$")

PIPELINE_PATTERNS = [
    re.compile(r"Execution started for pipeline \[(?P<name>[^\]]+)\]"),
    re.compile(r"Starting pipeline: \S*?(?P<name>[\w.-]+)\.hpl"),
    re.compile(r"^Pipeline: *(?P<name>[\w.-]+)", re.IGNORECASE),
]

# Most specific first: database and driver messages explain the failure
# better than the generic Hop exceptions that wrap them.
ROOT_ERROR_PATTERNS = [
    re.compile(r"PSQLException: (?P<msg>.+)"),
    re.compile(r"^(?P<msg>FATAL: .+)"),
    re.compile(r"^(?P<msg>Connection to \S+ refused.*)"),
    re.compile(r"(?P<msg>\w+ String : couldn't convert .+)"),
    re.compile(r"java\.io\.FileNotFoundException: (?P<msg>.+)"),
    re.compile(r"^(?P<msg>ERROR: (?:duplicate key|null value|new row|insert or update|column|relation|value too long|invalid input).+)"),
]

CAUSED_BY = re.compile(r"^Caused by: [\w.$]+: (?P<msg>.+)$")
DETAIL = re.compile(r"^\s*Detail: (?P<msg>.+?)(?:\s+Call getNextException.*)?$")
STACK_FRAME = re.compile(r"^\s*(?:at \S+\(.*\)|\.\.\. \d+ more)\s*$")
KEY_LINE = re.compile(
    r"ERROR|FATAL|Caused by:|Detail:|Exception|refused|couldn't convert|Batch entry|"
    r"failed to initialize|not a file|No such file",
)
TRANSFORM_COPY = re.compile(r"\.\d+$")


@dataclass
class ParsedLog:
    pipeline: str | None = None
    failed_transform: str | None = None
    root_error: str | None = None
    detail: str | None = None
    error_lines: list[str] = field(default_factory=list)

    @property
    def has_error(self) -> bool:
        return bool(self.root_error or self.error_lines)


def _split(line: str) -> tuple[str | None, str]:
    match = HOP_LINE.match(line)
    if match:
        return match["source"], match["message"]
    return None, line


def _truncate(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_LINE_LENGTH:
        return text
    return text[: MAX_LINE_LENGTH - 3] + "..."


def _find_pipeline(messages: list[str]) -> str | None:
    for pattern in PIPELINE_PATTERNS:
        for message in messages:
            match = pattern.search(message)
            if match:
                return _truncate(match["name"])
    return None


def _find_failed_transform(entries: list[tuple[str | None, str]], pipeline: str | None) -> str | None:
    for source, message in entries:
        if source and source not in ("HopRun", pipeline) and message.startswith("ERROR"):
            return _truncate(TRANSFORM_COPY.sub("", source))
    # Initialization failures are reported by the pipeline: "Transform [X.0] failed to initialize!"
    for _, message in entries:
        match = re.search(r"Transform \[(?P<name>[^\]]+)\] failed", message)
        if match:
            return _truncate(TRANSFORM_COPY.sub("", match["name"]))
    return None


def _find_root_error(messages: list[str]) -> str | None:
    for pattern in ROOT_ERROR_PATTERNS:
        for message in messages:
            match = pattern.search(message)
            if match:
                return _truncate(match["msg"])
    caused_by = [m["msg"] for m in map(CAUSED_BY.match, messages) if m and m["msg"].strip()]
    if caused_by:
        return _truncate(caused_by[-1])
    for message in messages:
        if "ERROR" in message:
            return _truncate(message)
    return None


def _find_detail(messages: list[str]) -> str | None:
    for message in messages:
        match = DETAIL.match(message)
        if match:
            return _truncate(match["msg"])
    return None


def _collect_error_lines(messages: list[str]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for message in messages:
        if STACK_FRAME.match(message) or not KEY_LINE.search(message):
            continue
        line = _truncate(message)
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
        if len(lines) == MAX_ERROR_LINES:
            break
    return lines


def parse_log(text: str) -> ParsedLog:
    """Parse a Hop console log (or a short error excerpt) into a ParsedLog."""
    entries = [_split(line) for line in text.splitlines()]
    messages = [message for _, message in entries]
    pipeline = _find_pipeline(messages)
    return ParsedLog(
        pipeline=pipeline,
        failed_transform=_find_failed_transform(entries, pipeline),
        root_error=_find_root_error(messages),
        detail=_find_detail(messages),
        error_lines=_collect_error_lines(messages),
    )
