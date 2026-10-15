"""Strict, bounded log parsing with stable source-line evidence identifiers."""

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re


MAX_BYTES = 256 * 1024
MAX_EVENTS = 200
MAX_MESSAGE = 2048
TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})"
)
TEXT_RECORD = re.compile(r"(\S+)\s+([A-Za-z]+)\s+(.+)")


class IncidentError(ValueError):
    """Invalid evidence, model output, or incident-report configuration."""


def decode_object(text: str, context: str) -> dict[str, object]:
    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise IncidentError(f"{context}: duplicate JSON field")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise IncidentError(f"{context}: non-finite JSON values are not allowed")

    try:
        result = json.loads(
            text, object_pairs_hook=unique_pairs, parse_constant=reject_constant
        )
    except IncidentError:
        raise
    except (ValueError, RecursionError) as error:
        raise IncidentError(f"{context}: invalid JSON") from error
    if not isinstance(result, dict):
        raise IncidentError(f"{context}: expected a JSON object")
    return result


@dataclass(frozen=True)
class Event:
    line: int
    timestamp: datetime
    level: str
    message: str

    @property
    def evidence_id(self) -> str:
        return f"L{self.line}"

    @property
    def utc_timestamp(self) -> str:
        return self.timestamp.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Evidence:
    source: str
    sha256: str
    events: tuple[Event, ...]


def read_evidence(path: Path, log_format: str) -> Evidence:
    if log_format not in {"text", "jsonl"}:
        raise IncidentError("Log format must be text or jsonl")
    if not path.is_file():
        raise IncidentError("Input must be a readable regular log file")
    with path.open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise IncidentError(f"Input exceeds the {MAX_BYTES}-byte limit; nothing was truncated")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise IncidentError("Input must be UTF-8") from error

    events: list[Event] = []
    for number, line in enumerate(text.split("\n"), 1):
        line = line.removesuffix("\r")
        if not line.strip():
            continue
        context = f"Line {number}"
        if log_format == "jsonl":
            record = decode_object(line, context)
            if set(record) != {"timestamp", "level", "message"}:
                raise IncidentError(
                    f"{context}: JSONL requires exactly timestamp, level, and message"
                )
            timestamp, level, message = (
                record["timestamp"], record["level"], record["message"]
            )
        else:
            match = TEXT_RECORD.fullmatch(line)
            if match is None:
                raise IncidentError(f"{context}: expected TIMESTAMP LEVEL message")
            timestamp, level, message = match.groups()

        if not isinstance(timestamp, str) or not TIMESTAMP.fullmatch(timestamp):
            raise IncidentError(f"{context}: timestamp requires ISO 8601 seconds and Z or an offset")
        try:
            instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            instant = instant.astimezone(UTC)
        except (ValueError, OverflowError) as error:
            raise IncidentError(f"{context}: invalid timestamp") from error
        if not isinstance(level, str) or not re.fullmatch(r"[A-Za-z]+", level):
            raise IncidentError(f"{context}: level must contain ASCII letters only")
        if not isinstance(message, str) or not message.strip():
            raise IncidentError(f"{context}: message must be a nonempty string")
        if len(message) > MAX_MESSAGE:
            raise IncidentError(f"{context}: message exceeds {MAX_MESSAGE} characters")
        try:
            message.encode("utf-8")
        except UnicodeEncodeError as error:
            raise IncidentError(f"{context}: message contains invalid Unicode") from error
        if any(
            (ord(character) < 32 or 127 <= ord(character) <= 159) and character != "\t"
            for character in message
        ):
            raise IncidentError(f"{context}: message contains control characters")
        normalized = level.upper()
        normalized = {"WARN": "WARNING", "ERR": "ERROR"}.get(normalized, normalized)
        events.append(Event(number, instant, normalized, message))
        if len(events) > MAX_EVENTS:
            raise IncidentError(f"Input exceeds {MAX_EVENTS} events; nothing was truncated")
    if not events:
        raise IncidentError("Input contains no events")
    events.sort(key=lambda event: (event.timestamp, event.line))
    return Evidence(path.name, hashlib.sha256(content).hexdigest(), tuple(events))
