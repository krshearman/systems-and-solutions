"""Summarize synthetic incident records without changing their input stream."""

from collections.abc import Iterable

from examples.refactor_guard.event_api import normalize_severity, parse_record


def summarize(lines: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in lines:
        if not line.strip():
            continue
        _, severity, _ = parse_record(line)
        normalized = normalize_severity(severity)
        counts[normalized] = counts.get(normalized, 0) + 1
    return counts
