"""Replacement internal API for synthetic timestamp|severity|message records."""


def parse_record(line: str) -> tuple[str, str, str]:
    timestamp, severity, message = line.rstrip("\r\n").split("|", 2)
    return timestamp, severity, message


def normalize_severity(severity: str) -> str:
    normalized = severity.strip().upper()
    return {"WARN": "WARNING", "ERR": "ERROR"}.get(normalized, normalized)
