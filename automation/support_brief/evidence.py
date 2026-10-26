"""Bounded support records; unknown values stay unknown."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from ..json_data import decode_object

MAX_BYTES = 65_536
MAX_SIGNALS = 25
FIELDS = {
    "id", "title", "area", "observed", "expected", "reproduction",
    "environment", "reported_impact",
}


class BriefError(ValueError):
    """Invalid support evidence, analysis, or configuration."""


def text(value: object, context: str, limit: int = 1000, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise BriefError(f"{context}: expected {'possibly empty' if empty else 'nonempty'} text, at most {limit} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise BriefError(f"{context}: invalid Unicode") from error
    if any((ord(char) < 32 and char not in "\n\t\r") or 127 <= ord(char) <= 159 for char in value):
        raise BriefError(f"{context}: control characters are not allowed")
    return value.strip()


@dataclass(frozen=True)
class Signal:
    id: str
    title: str
    area: str
    observed: str
    expected: str
    reproduction: tuple[str, ...]
    environment: str
    reported_impact: str

    @property
    def gaps(self) -> tuple[str, ...]:
        return tuple(
            label for label, value in (
                ("expected behavior", self.expected),
                ("reproduction steps", self.reproduction),
                ("environment", self.environment),
                ("reported impact", self.reported_impact),
            ) if not value
        )


@dataclass(frozen=True)
class Evidence:
    source: str
    sha256: str
    signals: tuple[Signal, ...]


def read_evidence(path: Path) -> Evidence:
    if not path.is_file():
        raise BriefError("Input must be a regular UTF-8 JSON file")
    with path.open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise BriefError(f"Input exceeds {MAX_BYTES} bytes; nothing was truncated")
    data = decode_object(content.decode("utf-8"), "Support evidence", BriefError)
    if set(data) != {"signals"} or not isinstance(data["signals"], list):
        raise BriefError("Input requires exactly a signals array")
    if not 1 <= len(data["signals"]) <= MAX_SIGNALS:
        raise BriefError(f"Input requires 1 to {MAX_SIGNALS} signals")
    signals: list[Signal] = []
    ids: set[str] = set()
    for record in data["signals"]:
        if not isinstance(record, dict) or set(record) != FIELDS:
            raise BriefError(f"Each signal requires exactly: {', '.join(sorted(FIELDS))}")
        identifier = record["id"]
        if not isinstance(identifier, str) or not re.fullmatch(r"S[0-9]{2,4}", identifier):
            raise BriefError("Signal IDs must be S followed by 2 to 4 ASCII digits")
        if identifier in ids:
            raise BriefError(f"Duplicate signal ID: {identifier}")
        ids.add(identifier)
        steps = record["reproduction"]
        if not isinstance(steps, list) or len(steps) > 8:
            raise BriefError(f"{identifier}: reproduction requires 0 to 8 steps")
        signals.append(Signal(
            identifier,
            text(record["title"], f"{identifier} title", 160),
            text(record["area"], f"{identifier} area", 80),
            text(record["observed"], f"{identifier} observed"),
            text(record["expected"], f"{identifier} expected", empty=True),
            tuple(text(step, f"{identifier} reproduction step", 500) for step in steps),
            text(record["environment"], f"{identifier} environment", 500, empty=True),
            text(record["reported_impact"], f"{identifier} reported impact", empty=True),
        ))
    return Evidence(path.name, hashlib.sha256(content).hexdigest(), tuple(signals))
