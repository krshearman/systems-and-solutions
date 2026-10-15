"""Deprecated synthetic helpers; retain unchanged as compatibility fixtures."""

from examples.refactor_guard.event_api import normalize_severity, parse_record


def parse_line(line: str) -> tuple[str, str, str]:
    return parse_record(line)


def normalize_level(level: str) -> str:
    return normalize_severity(level)
